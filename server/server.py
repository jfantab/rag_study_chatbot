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
from botocore.exceptions import ClientError
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
print("=" * 80)
print("🔐 ENCRYPTION KEY VALIDATION")
print("=" * 80)
encryption_key = os.getenv('CHAT_ENCRYPTION_KEY')
if encryption_key:
    print(f"✅ CHAT_ENCRYPTION_KEY is set")
    print(f"   Key length: {len(encryption_key)} characters")
    print(f"   Key prefix: {encryption_key[:10]}...")
    print(f"   Environment: {os.getenv('ENVIRONMENT', 'development')}")
else:
    print(f"⚠️  WARNING: CHAT_ENCRYPTION_KEY is NOT set!")
    print(f"   Server will generate a temporary key that changes on restart")
    print(f"   This will cause decryption failures for existing encrypted data")
print("=" * 80)

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
if allowed_origins == ['*']:
    print("⚠️  WARNING: CORS is allowing ALL origins. Set ALLOWED_ORIGINS environment variable for production.")
CORS(app, origins=allowed_origins)

# Configure max file upload size (100MB default, configurable via environment)
max_upload_mb = int(os.getenv('MAX_UPLOAD_SIZE_MB', '100'))
app.config['MAX_CONTENT_LENGTH'] = max_upload_mb * 1024 * 1024
print(f"📁 Max file upload size: {max_upload_mb}MB")

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
        print(f"Delete chat request: {data}")

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
    user_id = authenticated_user_id  # Use authenticated user ID from JWT

    print("user_id: ", user_id)

    try:
        client = boto3.client('dynamodb')
        
        # Query for all chat metadata for this user using the main table
        # Use PK = USER#user_id and SK begins_with CHAT# to get all chats for user
        pk = generate_user_pk(user_id)
        
        response = client.query(
            TableName='ChatSessions',
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk_prefix)',
            FilterExpression='entity_type = :entity_type',
            ExpressionAttributeValues={
                ':pk': {'S': pk},
                ':sk_prefix': {'S': 'CHAT#'},
                ':entity_type': {'S': 'chat_metadata'}
            },
            ScanIndexForward=False  # Descending order (newest first)
        )

        arr = []
        if 'Items' in response and response['Items']:
            for item in response['Items']:
                # Extract session_id from SK (format: CHAT#session_123)
                sk_value = item['SK']['S']
                session_id = sk_value.split('#', 1)[1] if '#' in sk_value else sk_value
                
                encrypted_chat_name = item.get('chat_name', {}).get('S', f'Chat {session_id}')

                # Get timestamp from created_at or use index
                timestamp_ms = item.get('created_at', {}).get('N', str(int(time.time() * 1000)))

                try:
                    # Try to decrypt the chat name, fallback to timestamp-based name if decryption fails
                    decrypted_name = encryption.decrypt_chat_name(encrypted_chat_name)
                except Exception as e:
                    print(f"⚠️  Warning: Failed to decrypt chat name for {session_id}: {str(e)}")
                    # Use timestamp-based placeholder name instead of encrypted gibberish
                    try:
                        from datetime import datetime
                        ts = int(timestamp_ms) / 1000
                        dt = datetime.fromtimestamp(ts)
                        decrypted_name = f"Chat {dt.strftime('%Y-%m-%d %H:%M')}"
                    except:
                        decrypted_name = f"Chat (encrypted)"

                # Get model_used if available
                model_used = item.get('model_used', {}).get('S', None)

                obj = {
                    "id": session_id,
                    "key": int(timestamp_ms),  # Use actual timestamp instead of index
                    "name": decrypted_name,
                    "model_used": model_used,  # Include model information
                }
                arr.append(obj)

        print(f"Found {len(arr)} chats for user {user_id}")
        return jsonify({"chats": arr}), 200
        
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

    print(f"🌊 Starting streaming response for: {question[:100]}...")

    # Convert S3 URLs to base64 (same as non-streaming)
    base64_images = None
    if image_urls and len(image_urls) > 0:
        base64_images = []
        for img in image_urls:
            if img.startswith('http'):
                try:
                    base64_img = download_s3_image_to_base64(img)
                    base64_images.append(base64_img)
                except Exception as e:
                    print(f"❌ Failed to download image: {e}")

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
            print(f"❌ Streaming error: {e}")
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
    from core.aws.dynamodb_service import use_new_message_table
    from core.aws.dynamodb_messages_service import get_messages_for_session

    msgs_id = request.args.get('msgId', default = "")
    user_id = authenticated_user_id  # Use authenticated user ID from JWT

    print(f"Requesting messages from {msgs_id} and {user_id}")

    # If new message table is enabled, try it first with fallback to old table
    if use_new_message_table():
        print("🆕 Using new message-based table (one item per message)")

        try:
            # Query the new message table
            chat_history = get_messages_for_session(user_id, msgs_id)

            if chat_history and len(chat_history) > 0:
                print(f"✅ Found {len(chat_history)} messages in new table")

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
                                import re
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
                            except Exception as e:
                                print(f"❌ Failed to generate presigned URL: {str(e)}")
                                presigned_urls.append(s3_url)

                        formatted_msg["image_urls"] = presigned_urls

                    msgs.append(formatted_msg)

                return jsonify({"msgs": msgs}), 200
            else:
                print(f"⚠️  No messages found in new table, falling back to old table")

        except Exception as e:
            print(f"⚠️  Error reading from new table: {str(e)}, falling back to old table")

    # Fallback to old table (or primary path if USE_NEW_MESSAGE_TABLE=false)
    print("📦 Using old table (entire history in one item)")

    client = boto3.client('dynamodb')

    # Try NEW format first: PK=USER#{user_id}, SK=HISTORY#{msg_id}
    pk = generate_user_pk(user_id)
    sk = generate_history_sk(msgs_id)

    print(f"🔍 Trying NEW format: PK={pk}, SK={sk}")

    try:
        response = client.get_item(
            TableName="ChatSessions",
            Key={
                'PK': {'S': pk},
                'SK': {'S': sk}
            }
        )

        # If not found, try OLD format: PK=CHAT#{msg_id}, SK=HISTORY
        if 'Item' not in response:
            print(f"⚠️  NEW format not found, trying OLD format...")
            old_pk = f"CHAT#{msgs_id}"
            old_sk = "HISTORY"
            print(f"🔍 Trying OLD format: PK={old_pk}, SK={old_sk}")

            response = client.get_item(
                TableName="ChatSessions",
                Key={
                    'PK': {'S': old_pk},
                    'SK': {'S': old_sk}
                }
            )

            if 'Item' not in response:
                print(f"❌ No messages found in either format")
                return jsonify({"msgs": []}), 200

            print(f"✅ Found messages in OLD format")
        else:
            print(f"✅ Found messages in NEW format")

        # Handle both ChatHistory (new) and messages (old) field names
        chat_history = None

        if 'ChatHistory' in response['Item']:
            # NEW format - ChatHistory field with per-message encryption
            print(f"📦 Using 'ChatHistory' field (NEW format)")
            try:
                history_data = response['Item'].get('ChatHistory', {'S': '[]'})['S']
                encrypted_history = json.loads(history_data)
                print(f"🔐 Attempting to decrypt {len(encrypted_history)} messages...")
                chat_history = encryption.decrypt_chat_history(encrypted_history)
                print(f"✅ Successfully decrypted chat history")
            except Exception as decrypt_error:
                print(f"❌ Failed to decrypt ChatHistory field: {str(decrypt_error)}")
                print(f"⚠️  This likely means CHAT_ENCRYPTION_KEY has changed or is missing")
                # Return empty messages instead of failing completely
                return jsonify({
                    "msgs": [],
                    "error": "Decryption failed - encryption key mismatch",
                    "details": "The data was encrypted with a different key. Check CHAT_ENCRYPTION_KEY environment variable."
                }), 200
        elif 'messages' in response['Item']:
            # OLD format - entire messages string encrypted
            print(f"📦 Using 'messages' field (OLD format)")
            messages_str = response['Item']['messages']['S']
            try:
                # Try to decrypt as text first (old encryption method)
                print(f"🔐 Attempting to decrypt messages string...")
                decrypted_messages_str = encryption.decrypt_text(messages_str)
                chat_history = json.loads(decrypted_messages_str)
                print(f"✅ Successfully decrypted OLD format messages")
            except Exception as decrypt_error:
                print(f"⚠️  Decryption failed, trying plain JSON parse: {str(decrypt_error)}")
                # If decryption fails, try parsing as plain JSON (unencrypted legacy data)
                try:
                    chat_history = json.loads(messages_str)
                    print(f"✅ Parsed as plain JSON (unencrypted)")
                except Exception as json_error:
                    print(f"❌ Failed to decrypt/parse messages: decrypt={decrypt_error}, json={json_error}")
                    return jsonify({
                        "msgs": [],
                        "error": "Failed to decrypt or parse messages",
                        "details": "Data may be corrupted or encrypted with wrong key"
                    }), 200
        else:
            print(f"❌ No ChatHistory or messages field found")
            print(f"Available fields: {list(response['Item'].keys())}")
            return jsonify({"msgs": []}), 200

        # Convert to expected format and ensure user message comes first in each pair
        msgs = []
        s3_client = boto3.client('s3')

        for msg in chat_history:
            # Handle both old format (msg/role) and new format (content/type)
            formatted_msg = {
                "role": msg.get("type", msg.get("role", "")),
                "msg": msg.get("content", msg.get("msg", ""))
            }
            # Add image URLs if present - convert to presigned URLs for secure access
            if "image_urls" in msg:
                presigned_urls = []
                for s3_url in msg["image_urls"]:
                    try:
                        # Extract bucket and key from S3 URL
                        import re
                        match = re.match(r'https://([^.]+)\.s3\.amazonaws\.com/(.+)', s3_url)
                        if match:
                            bucket_name = match.group(1)
                            file_key = match.group(2)

                            # Generate presigned URL (valid for 1 hour)
                            presigned_url = s3_client.generate_presigned_url(
                                'get_object',
                                Params={'Bucket': bucket_name, 'Key': file_key},
                                ExpiresIn=3600  # 1 hour
                            )
                            presigned_urls.append(presigned_url)
                            print(f"✅ Generated presigned URL for: {file_key}")
                        else:
                            # Invalid format, use original URL
                            presigned_urls.append(s3_url)
                    except Exception as e:
                        print(f"❌ Failed to generate presigned URL: {str(e)}")
                        # Fallback to original URL
                        presigned_urls.append(s3_url)

                formatted_msg["image_urls"] = presigned_urls
            msgs.append(formatted_msg)

        return jsonify({"msgs": msgs}), 200

    except Exception as e:
        print(f"Error retrieving messages: {str(e)}")
        return jsonify({"error": "Failed to retrieve messages"}), 500

""" DynamoDB Table Setup """
def ensure_chat_sessions_table_exists():
    """Create ChatSessions table if it doesn't exist"""
    try:
        client = boto3.client('dynamodb')

        # Check if table exists
        try:
            client.describe_table(TableName='ChatSessions')
            print("ChatSessions table already exists")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                raise e

        print("Creating ChatSessions table...")

        # Create the table
        client.create_table(
            TableName='ChatSessions',
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Wait for table to be created
        waiter = client.get_waiter('table_exists')
        waiter.wait(TableName='ChatSessions')

        print("ChatSessions table created successfully")
        return True

    except Exception as e:
        print(f"Error ensuring ChatSessions table exists: {str(e)}")
        return False

""" Main """
def main():
    """ Server sanity check """
    print('Server is working')
    print(f'Current model is {current_model_id}')

if __name__ == "__main__":
    from core.aws.dynamodb_service import ensure_all_tables_exist

    # Ensure DynamoDB tables exist before starting server
    if not ensure_all_tables_exist():
        print("⚠️  Warning: Failed to ensure all DynamoDB tables exist. Server may not work properly.")

    # Check if new message table should be used
    from core.aws.dynamodb_service import use_new_message_table
    if use_new_message_table():
        print("🆕 Server configured to use NEW message-based table (one item per message)")
        print("   Set USE_NEW_MESSAGE_TABLE=false to revert to old approach")
    else:
        print("📦 Server configured to use OLD approach (entire history in one item)")
        print("   Set USE_NEW_MESSAGE_TABLE=true to enable new message-based table")

    # Run server sanity check before starting
    main()

    # Get debug mode from environment (default False for production safety)
    debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'

    print(f"🚀 Starting server on port {PORT} (debug={'ON' if debug_mode else 'OFF'})")
    app.run(host="0.0.0.0", port=PORT, debug=debug_mode)
