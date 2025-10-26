"""
Message management routes for chat message operations
"""
import json
from flask import Blueprint, jsonify, request

from core.services.auth_service import require_auth
from core.services.chat_service import delete_message_from_history, edit_message_and_regenerate
from core.services.model_service import get_current_model_info
from core.aws.bedrock_wrapper import query_bedrock
from constants import BEDROCK_API_URL

message_bp = Blueprint('messages', __name__)


@message_bp.route("/delete_message", methods=["POST"])
@require_auth
def delete_message(authenticated_user_id):
    """
    Delete a message from chat history

    AUTOMATIC BEHAVIOR:
    - When deleting a USER message → Also deletes the associated AI response
    - When deleting an AI message → Only deletes that message

    Request body:
    - msg_id (required): Chat session ID
    - message_index (for old table) OR message_timestamp (for new table, recommended)
    - delete_next (optional): Override automatic behavior (defaults to auto-determined)
    """
    try:
        data = request.get_json()

        if 'msg_id' not in data:
            return jsonify({"error": "msg_id is required"}), 400

        # Support both message_index (old) and message_timestamp (new)
        if 'message_index' not in data and 'message_timestamp' not in data:
            return jsonify({"error": "Either message_index or message_timestamp is required"}), 400

        msg_id = data["msg_id"]
        message_index = data.get("message_index")
        message_timestamp = data.get("message_timestamp")
        # delete_next is now auto-determined by message type if not explicitly provided
        delete_next = data.get("delete_next", None)

        # Call service function
        result = delete_message_from_history(
            user_id=authenticated_user_id,
            msg_id=msg_id,
            message_index=message_index,
            message_timestamp=message_timestamp,
            delete_next=delete_next
        )

        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify({"error": result.get('error')}), result.get('status_code', 500)

    except Exception as e:
        return jsonify({"error": f"Failed to delete message: {str(e)}"}), 500


@message_bp.route("/edit_message", methods=["POST"])
@require_auth
def edit_message(authenticated_user_id):
    """
    Edit a user message and get a new AI response

    Accepts either:
    - message_index (for old table compatibility)
    - message_timestamp (for new table, recommended)
    """
    try:
        data = request.get_json()

        if 'msg_id' not in data or 'new_content' not in data:
            return jsonify({"error": "msg_id and new_content are required"}), 400

        # Support both message_index (old) and message_timestamp (new)
        if 'message_index' not in data and 'message_timestamp' not in data:
            return jsonify({"error": "Either message_index or message_timestamp is required"}), 400

        msg_id = data["msg_id"]
        message_index = data.get("message_index")
        message_timestamp = data.get("message_timestamp")
        new_content = data["new_content"]

        # Get current model ID
        current_model = get_current_model_info()
        current_model_id = current_model.get('model_id', 'anthropic.claude-3-5-sonnet-20240620-v1:0')

        # Create query function for AI response generation
        def query_fn(content):
            return query_bedrock(content, "", authenticated_user_id, None, None, current_model_id, BEDROCK_API_URL)

        # Call service function
        result = edit_message_and_regenerate(
            user_id=authenticated_user_id,
            msg_id=msg_id,
            message_index=message_index,
            message_timestamp=message_timestamp,
            new_content=new_content,
            query_fn=query_fn
        )

        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify({"error": result.get('error')}), result.get('status_code', 500)

    except Exception:
        return jsonify({"error": "Failed to edit message"}), 500
