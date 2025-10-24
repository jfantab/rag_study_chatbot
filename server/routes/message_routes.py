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
        print(f"🔴 DELETE MESSAGE REQUEST RECEIVED:")
        print(f"   Raw data: {data}")
        print(f"   User ID: {authenticated_user_id}")

        if 'msg_id' not in data:
            print(f"❌ ERROR: msg_id missing from request")
            return jsonify({"error": "msg_id is required"}), 400

        # Support both message_index (old) and message_timestamp (new)
        if 'message_index' not in data and 'message_timestamp' not in data:
            print(f"❌ ERROR: Neither message_index nor message_timestamp provided")
            return jsonify({"error": "Either message_index or message_timestamp is required"}), 400

        msg_id = data["msg_id"]
        message_index = data.get("message_index")
        message_timestamp = data.get("message_timestamp")
        # delete_next is now auto-determined by message type if not explicitly provided
        delete_next = data.get("delete_next", None)

        print(f"📋 DELETE PARAMS:")
        print(f"   msg_id: {msg_id}")
        print(f"   message_index: {message_index} (type: {type(message_index)})")
        print(f"   message_timestamp: {message_timestamp} (type: {type(message_timestamp)})")
        print(f"   delete_next: {delete_next}")

        # Call service function
        result = delete_message_from_history(
            user_id=authenticated_user_id,
            msg_id=msg_id,
            message_index=message_index,
            message_timestamp=message_timestamp,
            delete_next=delete_next
        )

        print(f"✅ DELETE RESULT: {result}")

        if result.get('success'):
            return jsonify(result), 200
        else:
            print(f"❌ DELETE FAILED: {result.get('error')}")
            return jsonify({"error": result.get('error')}), result.get('status_code', 500)

    except Exception as e:
        print(f"❌ EXCEPTION in delete_message endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
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

        print(f"Editing message from {msg_id} for user {authenticated_user_id}")
        if message_timestamp:
            print(f"  Using timestamp: {message_timestamp}")
        elif message_index is not None:
            print(f"  Using index: {message_index}")

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

    except Exception as e:
        print(f"Error in edit_message endpoint: {str(e)}")
        return jsonify({"error": "Failed to edit message"}), 500
