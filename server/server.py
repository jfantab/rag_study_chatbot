import os
import json
import base64
import uuid
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
from setup import setup
from constants import *
import boto3
from core.services.encryption import encryption
from core.services.auth_service import *
from core.aws.bedrock_service import *
from core.services.chat_service import *
from core.aws.dynamodb_service import *
from core.services.model_service import (
    set_models, set_current_model, get_current_model_id,
    change_model as change_model_service,
    get_models_list, get_current_model_info
)
from core.aws.s3_utils import *
from core.aws.cognito_service import *
from core.services.pdf_service import *
import re

load_dotenv()

# Validate encryption key is loaded
encryption_key = os.getenv('CHAT_ENCRYPTION_KEY')
if not encryption_key:
    print(f"⚠️  WARNING: CHAT_ENCRYPTION_KEY is NOT set!")

# Initialize Bedrock clients
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime', region_name=AWS_REGION)
bedrock_runtime_client = boto3.client('bedrock-runtime', region_name=AWS_REGION)
textract_client = boto3.client('textract', region_name=AWS_REGION)

# Knowledge Base configuration
KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID", "ADEGC5Q4KM")

# Validate environment variables
validate_environment()

""" Flask Application Setup """
app = Flask(__name__)

# Configure CORS - restrict to specific origins in production
allowed_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',')
CORS(app, origins=allowed_origins)

# Configure max file upload size (100MB default, configurable via environment)
max_upload_mb = int(os.getenv('MAX_UPLOAD_SIZE_MB', '100'))
app.config['MAX_CONTENT_LENGTH'] = max_upload_mb * 1024 * 1024

# Use imported models and set current model
models = MODELS
current_model_id = DEFAULT_MODEL_ID

# Initialize model service with current configuration
set_models(MODELS)
set_current_model(DEFAULT_MODEL_ID)

""" LangChain and AWS setup """
llm = setup()

# Register route blueprints
from routes.auth_routes import auth_bp
from routes.image_routes import image_bp
from routes.chat_routes import chat_bp
from routes.message_routes import message_bp
from routes.file_routes import file_bp

app.register_blueprint(auth_bp)
app.register_blueprint(image_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(message_bp)
app.register_blueprint(file_bp)

""" Error Handlers """
@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file size limit exceeded errors"""
    return jsonify({
        "error": "File too large",
        "message": f"Maximum file size is {max_upload_mb}MB",
        "max_size_mb": max_upload_mb
    }), 413

""" Health Check """
@app.route("/")
def alive():
    return "Alive", 200

@app.route("/delete_chat", methods=["POST"])
@require_auth
def del_chat(authenticated_user_id):
    """Delete a chat session"""
    try:
        data = request.get_json()

        if 'msg_id' not in data:
            return jsonify({"error": "msg_id is required"}), 400

        msg_id = data["msg_id"]
        result = delete_chat_session(authenticated_user_id, msg_id)

        if result.get('success'):
            return jsonify({"message": result['message']}), 200
        else:
            return jsonify({"error": result['error']}), result.get('status_code', 500)

    except Exception as e:
        print(f"❌ Error in delete_chat route: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/change_model", methods=["POST"])
def change_model():
    """Change the current AI model"""
    global current_model_id
    try:
        data = request.get_json()

        if not data or "model_name" not in data:
            return jsonify({"error": "model_name is required"}), 400

        result = change_model_service(data["model_name"])

        if result.get('success'):
            # Update global variable for backward compatibility
            current_model_id = result['model_id']
            return jsonify(result), 200
        else:
            return jsonify(result), result.get('status_code', 400)

    except Exception as e:
        print(f"Error changing model: {str(e)}")
        return jsonify({"error": "Failed to change model"}), 500

@app.route("/get_models", methods=["GET"])
def get_models():
    """Get list of available models with their categories"""
    try:
        result = get_models_list()
        return jsonify(result), 200
    except Exception as e:
        print(f"Error getting models: {str(e)}")
        return jsonify({"error": "Failed to get models"}), 500

@app.route("/get_current_model", methods=["GET"])
def get_current_model():
    """Get the currently selected model"""
    try:
        result = get_current_model_info()
        return jsonify(result), 200
    except Exception as e:
        print(f"Error getting current model: {str(e)}")
        return jsonify({"error": "Failed to get current model"}), 500

""" Retrieval """
@app.route("/get_chat_names", methods=["GET"])
@require_auth
def get_chat_names(authenticated_user_id):
    """Get list of chat sessions for the authenticated user"""
    from core.services.chat_service import get_chat_list

    user_id = authenticated_user_id

    try:
        chats = get_chat_list(user_id)
        return jsonify({"chats": chats}), 200
    except Exception as e:
        print(f"Error getting chat names: {str(e)}")
        # Return empty array instead of error to prevent client-side errors
        return jsonify({"chats": []}), 200

@app.route("/chat_stream", methods=["POST"])
@require_auth
def chat_stream(authenticated_user_id):
    """
    Server-Sent Events endpoint for streaming chat responses
    """
    data = request.get_json()

    if 'msg' not in data or 'msg_id' not in data:
        return jsonify({"error": "Missing required fields"}), 400

    question = data["msg"]
    msg_id = data["msg_id"]
    user_id = authenticated_user_id

    image_urls = data.get("image_urls", [])
    files = data.get("files", [])

    # Convert S3 URLs to base64 (same as non-streaming)
    base64_images = None
    if image_urls and len(image_urls) > 0:
        base64_images = []
        for img in image_urls:
            if img.startswith('http'):
                try:
                    base64_img, media_type = download_s3_image_to_base64(img)
                    base64_images.append(base64_img)
                except Exception:
                    pass  # Skip failed image downloads

    def generate():
        """Generator function for SSE streaming"""
        try:
            full_response = ""

            # Stream from Bedrock
            for chunk in retrieve_and_generate_bedrock_stream(
                user_input=question,
                session_id=msg_id,
                model_id=current_model_id,
                user_id=user_id,
                images=base64_images,
                files=files
            ):
                full_response += chunk

                # Send chunk to client via SSE
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            # Send completion signal
            yield f"data: {json.dumps({'done': True, 'full_text': full_response})}\n\n"

            # Save to DynamoDB (after streaming completes)
            # Use update_chat_history to respect USE_NEW_MESSAGE_TABLE setting
            update_chat_history(user_id, msg_id, question, full_response, image_urls, files)

        except Exception as e:
            print(f"❌ Error in chat_stream: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    # Return SSE response
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
            'Connection': 'keep-alive'
        }
    )

""" History """

@app.route("/retrieve_messages", methods=["GET"])
@require_auth
def retrieve_messages(authenticated_user_id):
    """Retrieve chat messages for a session (uses new ChatMessages table)"""
    from core.aws.dynamodb_messages_service import get_messages_for_session

    msgs_id = request.args.get('msgId', default="")
    user_id = authenticated_user_id

    try:
        # Query the ChatMessages table
        chat_history = get_messages_for_session(user_id, msgs_id)

        if not chat_history:
            return jsonify({"msgs": []}), 200

        # Convert to expected format for frontend
        msgs = []
        s3_client = boto3.client('s3')

        for msg in chat_history:
            formatted_msg = {
                "role": msg.get("type", ""),
                "msg": msg.get("content", ""),
                "timestamp": msg.get("timestamp", "")  # Include timestamp for edit/delete
            }

            # Add image URLs if present - convert to presigned URLs
            if "image_urls" in msg:
                presigned_urls = []
                for s3_url in msg["image_urls"]:
                    try:
                        match = re.match(r'https://([^.]+)\.s3\.amazonaws\.com/(.+)', s3_url)
                        if match:
                            bucket_name = match.group(1)
                            file_key = match.group(2)

                            presigned_url = s3_client.generate_presigned_url(
                                'get_object',
                                Params={'Bucket': bucket_name, 'Key': file_key},
                                ExpiresIn=3600
                            )
                            presigned_urls.append(presigned_url)
                        else:
                            presigned_urls.append(s3_url)
                    except Exception:
                        presigned_urls.append(s3_url)

                formatted_msg["image_urls"] = presigned_urls

            # Add file attachments if present
            if "file_attachments" in msg:
                formatted_msg["file_attachments"] = msg["file_attachments"]

            msgs.append(formatted_msg)

        return jsonify({"msgs": msgs}), 200

    except Exception as e:
        print(f"Error retrieving messages: {str(e)}")
        return jsonify({"error": "Failed to retrieve messages"}), 500

if __name__ == "__main__":
    from core.aws.dynamodb_service import ensure_all_tables_exist

    # Ensure DynamoDB tables exist before starting server
    ensure_all_tables_exist()

    # Get debug mode from environment (default False for production safety)
    debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'

    app.run(host="0.0.0.0", port=PORT, debug=debug_mode)
