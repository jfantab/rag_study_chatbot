"""
Chat session routes for creating and managing chat sessions
"""
import json
from flask import Blueprint, jsonify, request
from botocore.exceptions import ClientError

from core.services.auth_service import require_auth
from core.services.chat_service import create_new_chat, query_with_session_context, update_chat_history
from core.services.model_service import get_current_model_info
from core.utils.message_utils import (
    validate_chat_request,
    process_image_attachments,
    separate_pdf_files,
    normalize_response_format
)
from core.utils.pdf_utils import process_pdf_with_hybrid
from core.aws.bedrock_wrapper import query_bedrock
from constants import BEDROCK_API_URL, DEFAULT_MODEL_ID

chat_bp = Blueprint('chat', __name__)


@chat_bp.route("/new_chat", methods=["POST"])
@require_auth
def new_chat(authenticated_user_id):
    """Create a new chat session"""
    try:
        data = request.get_json()

        if 'msg_id' not in data:
            return jsonify({"error": "msg_id is not found in request object."}), 400

        if 'chat_name' not in data:
            return jsonify({"error": "chat_name is required"}), 400

        msg_id = data["msg_id"]
        chat_name = data["chat_name"]

        # Get current model ID
        current_model = get_current_model_info()
        model_id = current_model.get('current_model_id', DEFAULT_MODEL_ID)

        # Create the chat
        result = create_new_chat(
            user_id=authenticated_user_id,
            msg_id=msg_id,
            chat_name=chat_name,
            model_id=model_id
        )

        if result.get('success'):
            return jsonify({
                "success": True,
                "message": "Chat created successfully"
            }), 200
        else:
            return jsonify({"error": "Failed to create new chat"}), 500

    except Exception:
        return jsonify({"error": "Failed to create new chat"}), 500


@chat_bp.route("/chat", methods=["POST"])
@require_auth
def chat_with_retrieval(authenticated_user_id):
    """Send a message and get AI response"""
    try:
        data = request.get_json()

        # Validate request
        is_valid, error_response, validated_data = validate_chat_request(data)
        if not is_valid:
            return error_response

        question = validated_data['question']
        msg_id = validated_data['msg_id']
        images = validated_data['images']
        image_urls = validated_data['image_urls']
        files = validated_data['files']
        user_id = authenticated_user_id

        # Get current model ID
        current_model = get_current_model_info()
        current_model_id = current_model.get('current_model_id', DEFAULT_MODEL_ID)

        # Process image attachments
        image_urls = process_image_attachments(images, image_urls, user_id, msg_id)

        # Separate PDF files from other file types
        pdf_files, other_files = separate_pdf_files(files)

        # Process PDFs with hybrid approach
        if pdf_files:
            try:
                answer = process_pdf_with_hybrid(question, pdf_files, msg_id, user_id)
            except Exception:
                # Fallback to regular processing
                answer = query_bedrock(question, msg_id, user_id, image_urls if image_urls else None, files if files else None, current_model_id, BEDROCK_API_URL)
                answer = json.loads(answer)
                answer = answer["body"]["answer"]
        else:
            # No PDF attached to this message.
            # Check for session context or perform a generic query.
            answer = query_with_session_context(
                question, msg_id, user_id, image_urls, other_files,
                query_bedrock_fn=lambda q, m, u, i, f: query_bedrock(q, m, u, i, f, current_model_id, BEDROCK_API_URL)
            )

        # Normalize response format
        answer = normalize_response_format(answer)

        # Generate captions/summaries for attachments
        image_captions = None
        file_summaries = None

        # Generate image captions if images are present
        if image_urls and len(image_urls) > 0:
            image_captions = []
            # Use the first sentence(s) of AI's response as the caption
            # This captures what the AI understood about the image
            caption = answer.split('.')[0] + '.' if '.' in answer else answer[:200]
            for _ in image_urls:
                image_captions.append(caption)
            print(f"📷 Generated {len(image_captions)} image caption(s) from AI response")

        # Generate file summaries if files are present
        if files and len(files) > 0:
            file_summaries = []
            for file_data in files:
                file_name = file_data.get('name', 'unknown')
                # Create a brief summary using file name and AI's response
                summary = f"File '{file_name}': {answer[:300]}..." if len(answer) > 300 else f"File '{file_name}': {answer}"
                file_summaries.append(summary)
            print(f"📄 Generated {len(file_summaries)} file summary(ies) from AI response")

        # Update chat history in DynamoDB with captions
        update_chat_history(user_id, msg_id, question, answer, image_urls, files, image_captions, file_summaries)

        response = jsonify({"answer": answer})

        # Enable Access-Control-Allow-Origin
        response.headers.add("Access-Control-Allow-Origin", "*")

        return response, 200

    except ClientError as e:
        if e.response['Error']['Code'] == 'ValidationException':
            return jsonify({"error": "Invalid session ID or user ID provided"}), 400
        else:
            return jsonify({"error": f"Database error: {e.response['Error']['Message']}"}), 500
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
