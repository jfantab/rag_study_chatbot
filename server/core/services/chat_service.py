"""
Chat management service for creating, deleting, and managing chat sessions

Supports both:
1. Old approach: Entire chat history in one item (legacy)
2. New approach: One item per message (recommended - controlled by USE_NEW_MESSAGE_TABLE env var)
"""
import boto3
import json
import re
from datetime import datetime
from botocore.exceptions import ClientError
from core.aws.dynamodb_service import get_history_pk, get_chat_pk, get_chat_sk, get_current_timestamp, use_new_message_table
from core.aws.dynamodb_messages_service import (
    save_individual_message,
    get_messages_for_session,
    update_single_message,
    delete_single_message,
    generate_message_pk
)
from core.services.pdf_processing import PDFProcessor
from core.services.encryption import encryption


def create_new_chat(user_id: str, msg_id: str, chat_name: str, model_id: str) -> dict:
    """
    Create a new chat session with metadata only (no initial greeting message)

    Args:
        user_id: User ID who owns the chat
        msg_id: Unique message/session ID
        chat_name: Name of the chat session
        model_id: AI model ID to use for this chat

    Returns:
        Dictionary with success status
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('ChatMetadata')

        current_time = get_current_timestamp()

        # Create chat metadata record
        chat_metadata = {
            'PK': get_chat_pk(user_id),
            'SK': get_chat_sk(msg_id),
            'GSI1PK': get_chat_pk(user_id),
            'entity_type': 'chat_metadata',
            'chat_name': encryption.encrypt_chat_name(chat_name),
            'created_at': current_time,
            'updated_at': current_time,
            'message_count': 0,  # Start with 0 messages - user message will be first
            'model_used': model_id
        }

        table.put_item(Item=chat_metadata)

        # No initial greeting message - conversation starts with user's first message
        # This aligns with the new ChatMessages table architecture where conversations
        # are user-initiated and each message is a separate DynamoDB item

        return {
            "success": True
        }

    except Exception as e:
        print(f"Error creating new chat: {str(e)}")
        raise


def delete_chat_session(user_id: str, msg_id: str) -> dict:
    """
    Delete a chat session including metadata, history, and associated S3 images.
    This function handles both the new and old DynamoDB key schemas for history items.

    Args:
        user_id: User ID who owns the chat
        msg_id: Message/session ID to delete

    Returns:
        Dictionary with success status and message
    """
    client = boto3.client('dynamodb')
    table_name = 'ChatMetadata'

    # Define keys for both new and old formats
    chat_metadata_key = {
        'PK': {'S': get_chat_pk(user_id)},
        'SK': {'S': get_chat_sk(msg_id)}
    }
    new_history_key = {
        'PK': {'S': get_chat_pk(user_id)},
        'SK': {'S': f'HISTORY#{msg_id}'}
    }
    old_history_key = {
        'PK': {'S': get_history_pk(msg_id)},
        'SK': {'S': 'HISTORY'}
    }

    try:
        # --- Step 1: Retrieve history for S3 cleanup ---
        history_item = None
        try:
            # Try fetching with the new key format first
            response = client.get_item(TableName=table_name, Key=new_history_key)
            history_item = response.get('Item')

            if not history_item:
                # If not found, try the old key format
                response = client.get_item(TableName=table_name, Key=old_history_key)
                history_item = response.get('Item')

            if history_item:
                # --- Step 2: Delete associated S3 images ---
                encrypted_history_str = history_item.get('ChatHistory', {}).get('S') or history_item.get('messages', {}).get('S', '[]')
                
                # Decrypt based on field name
                if 'ChatHistory' in history_item:
                    chat_history = encryption.decrypt_chat_history(json.loads(encrypted_history_str))
                else:
                    chat_history = json.loads(encryption.decrypt_text(encrypted_history_str))

                image_urls_to_delete = [
                    url for msg in chat_history if 'image_urls' in msg for url in msg['image_urls']
                ]

                if image_urls_to_delete:
                    print(f"Deleting {len(image_urls_to_delete)} images from S3...")
                    s3_client = boto3.client('s3')
                    for s3_url in image_urls_to_delete:
                        try:
                            match = re.match(r'https://([^.]+)\\.s3\\.amazonaws\\.com/(.+)', s3_url)
                            if match:
                                bucket_name, file_key = match.groups()
                                s3_client.delete_object(Bucket=bucket_name, Key=file_key)
                                print(f"Deleted S3 image: {file_key}")
                        except Exception as e:
                            print(f"Failed to delete S3 image {s3_url}: {str(e)}")
        except Exception as e:
            print(f"Warning: Could not retrieve chat history for S3 cleanup. Proceeding with DB deletion. Error: {str(e)}")

        # --- Step 3: Delete DynamoDB items ---
        print("Deleting chat metadata...", chat_metadata_key)
        client.delete_item(TableName=table_name, Key=chat_metadata_key)

        print("Deleting chat history (new format)...", new_history_key)
        client.delete_item(TableName=table_name, Key=new_history_key)

        print("Deleting chat history (old format, for cleanup)...", old_history_key)
        client.delete_item(TableName=table_name, Key=old_history_key)

        print("Chat deleted successfully from DynamoDB (including S3 images).")
        return {"success": True, "message": "Chat deleted successfully"}

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        print(f"DynamoDB ClientError: {error_code} - {error_msg}")
        return {"success": False, "error": f"Database error: {error_msg}", "status_code": 500}

    except Exception as e:
        print(f"Error deleting chat: {str(e)}")
        raise


def query_with_session_context(question: str, msg_id: str, user_id: str, images=None, other_files=None, query_bedrock_fn=None):
    """
    Queries Bedrock with the context of a PDF associated with the chat session.
    If no PDF is associated, performs a generic query.

    Args:
        question: User's question
        msg_id: Message/session ID
        user_id: User ID
        images: Optional list of images
        other_files: Optional list of other files
        query_bedrock_fn: Function to call for generic bedrock queries

    Returns:
        Answer text from Bedrock
    """
    try:
        # Classify intent first - if it's general chat/greeting, skip PDF/KB logic entirely
        from core.services.intent_classifier import classify_intent
        intent = classify_intent(question)
        if intent in ['GENERAL_CHAT', 'GREETING']:
            print(f"🎯 Intent: {intent} - Skipping session context check, going directly to LLM")
            answer = query_bedrock_fn(question, msg_id, user_id, images, other_files)

            # Handle both direct Bedrock (string) and Lambda (JSON) responses
            if isinstance(answer, str) and not answer.startswith('{'):
                return answer  # Direct Bedrock response
            else:
                # Lambda response
                answer = json.loads(answer) if isinstance(answer, str) else answer
                return answer["body"]["answer"]

        # 1. Get associated_pdf_hash from ChatMetadata table
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('ChatMetadata')

        response = table.get_item(
            Key={
                'PK': get_chat_pk(user_id),
                'SK': get_chat_sk(msg_id)
            }
        )

        chat_item = response.get('Item')
        associated_pdf_hash = chat_item.get('associated_pdf_hash') if chat_item else None

        if associated_pdf_hash:
            # A PDF is associated with this session.
            print(f"Found associated PDF hash: {associated_pdf_hash} for session: {msg_id}")
            pdf_processor = PDFProcessor()
            kb_status = pdf_processor.check_kb_document_exists(associated_pdf_hash)

            if kb_status.get('exists') and kb_status.get('status') == 'indexed':
                # If indexed, query the KB with fallback to direct LLM
                print(f"PDF is indexed. Querying knowledge base.")
                try:
                    kb_answer = pdf_processor.query_knowledge_base(question, associated_pdf_hash, user_id)

                    # Check if KB returned a meaningful answer
                    if kb_answer and kb_answer.strip() and kb_answer != 'No answer found in knowledge base.':
                        print(f"✅ Knowledge base provided answer")
                        return kb_answer
                    else:
                        print(f"⚠️ Knowledge base returned no answer, falling back to direct LLM")
                        # Fallback to generic query
                        answer = query_bedrock_fn(question, msg_id, user_id, images, other_files)
                        if isinstance(answer, str) and not answer.startswith('{'):
                            return answer
                        else:
                            answer = json.loads(answer) if isinstance(answer, str) else answer
                            return answer["body"]["answer"]

                except Exception as kb_error:
                    print(f"❌ Knowledge base query failed: {str(kb_error)}, falling back to direct LLM")
                    # Fallback to generic query on KB error
                    answer = query_bedrock_fn(question, msg_id, user_id, images, other_files)
                    if isinstance(answer, str) and not answer.startswith('{'):
                        return answer
                    else:
                        answer = json.loads(answer) if isinstance(answer, str) else answer
                        return answer["body"]["answer"]
            else:
                # If not indexed yet, try to answer with general LLM knowledge
                print(f"PDF is not yet indexed (status: {kb_status.get('status')}).")
                print("Falling back to general Bedrock query without KB context")

                try:
                    # Attempt to answer with general knowledge
                    answer = query_bedrock_fn(question, msg_id, user_id, images, other_files)

                    # Handle both direct Bedrock (string) and Lambda (JSON) responses
                    if isinstance(answer, str) and not answer.startswith('{'):
                        bedrock_answer = answer
                    else:
                        answer = json.loads(answer) if isinstance(answer, str) else answer
                        bedrock_answer = answer["body"]["answer"]

                    # Add a note about the document still processing
                    enhanced_answer = f"""{bedrock_answer}

📋 *Note: Your document is still being indexed in the background. Once indexing completes, I'll be able to provide more detailed answers based on your specific document content.*"""

                    return enhanced_answer

                except Exception as bedrock_error:
                    print(f"⚠️ General Bedrock query also failed: {str(bedrock_error)}")
                    return "Your document is still being processed and is not yet available in the knowledge base. Please try your query again in a few moments."
        else:
            # No PDF associated, so just do a generic bedrock query.
            print("No associated PDF. Performing generic query.")
            answer = query_bedrock_fn(question, msg_id, user_id, images, other_files)

            # Handle both direct Bedrock (string) and Lambda (JSON) responses
            if isinstance(answer, str) and not answer.startswith('{'):
                return answer  # Direct Bedrock response
            else:
                # Lambda response
                answer = json.loads(answer) if isinstance(answer, str) else answer
                return answer["body"]["answer"]

    except Exception as e:
        print(f"Error in query_with_session_context: {str(e)}")
        # Fallback to generic query on error
        answer = query_bedrock_fn(question, msg_id, user_id, images, other_files)

        # Handle both direct Bedrock (string) and Lambda (JSON) responses
        if isinstance(answer, str) and not answer.startswith('{'):
            return answer  # Direct Bedrock response
        else:
            # Lambda response
            answer = json.loads(answer) if isinstance(answer, str) else answer
            return answer["body"]["answer"]


def update_chat_history(user_id: str, msg_id: str, question: str, answer: str, image_urls: list = None, files: list = None, image_captions: list = None, file_summaries: list = None):
    """
    Update chat history in DynamoDB using one-item-per-message approach

    Args:
        user_id: User ID who owns the chat
        msg_id: Message/session ID
        question: User's question
        answer: AI's answer
        image_urls: Optional list of image URLs
        files: Optional list of file data
        image_captions: Optional list of image captions for context
        file_summaries: Optional list of file summaries for context

    Returns:
        None
    """
    from core.utils.message_utils import extract_file_metadata

    # Prepare file metadata if files are present
    file_metadata = None
    if files:
        file_metadata = extract_file_metadata(files)

    print("🆕 Saving messages to ChatMessages table (one item per message)")

    # Save user message
    save_individual_message(
        user_id=user_id,
        session_id=msg_id,
        message_type='human',
        content=question,
        image_urls=image_urls,
        file_attachments=file_metadata,
        image_captions=image_captions,
        file_summaries=file_summaries
    )

    # Save AI response
    save_individual_message(
        user_id=user_id,
        session_id=msg_id,
        message_type='ai',
        content=answer
    )

    print(f"✅ Saved 2 messages to ChatMessages table (Cost: 2 WCUs)")


def delete_message_from_history(user_id: str, msg_id: str, message_index: int = None, message_timestamp: str = None, delete_next: bool = None) -> dict:
    """
    Delete a message from chat history

    When deleting a user message, automatically deletes the associated AI response.
    When deleting an AI message, only deletes that message.

    Args:
        user_id: User ID who owns the chat
        msg_id: Message/session ID
        message_index: 0-based index of message to delete (used with old table)
        message_timestamp: ISO8601 timestamp of message to delete (used with new table)
        delete_next: Whether to also delete the next message (auto-determined if None)

    Returns:
        Dictionary with success status and deleted count
    """
    from core.aws.dynamodb_service import generate_user_pk, generate_history_sk

    # If new message table is enabled, use direct delete
    if use_new_message_table():
        print("🆕 Using new message-based table for delete (Cost: 1-2 WCUs)")

        try:
            # Get all messages to find the one to delete (and potentially next one)
            print(f"🔍 Fetching messages for session: user_id={user_id}, msg_id={msg_id}")
            messages = get_messages_for_session(user_id, msg_id)
            print(f"📋 Retrieved {len(messages)} messages from DB")

            if message_timestamp:
                # Find message by timestamp
                print(f"🔍 Searching for message with timestamp: {message_timestamp}")
                print(f"   Available timestamps: {[msg.get('timestamp') for msg in messages]}")

                target_idx = None
                for i, msg in enumerate(messages):
                    msg_ts = msg.get('timestamp')
                    print(f"   Comparing: '{msg_ts}' == '{message_timestamp}' ? {msg_ts == message_timestamp}")
                    if msg_ts == message_timestamp:
                        target_idx = i
                        break

                if target_idx is None:
                    print(f"❌ Message not found with timestamp: {message_timestamp}")
                    print(f"   Available timestamps in DB:")
                    for i, msg in enumerate(messages):
                        print(f"     [{i}] {msg.get('timestamp')} ({msg.get('type')})")
                    return {"success": False, "error": "Message not found", "status_code": 404}

                print(f"✅ Found message at index {target_idx}")

            elif message_index is not None:
                # Use index to find message
                if message_index >= len(messages):
                    return {"success": False, "error": "Message index out of range", "status_code": 400}
                target_idx = message_index
                message_timestamp = messages[target_idx].get('timestamp')
            else:
                return {"success": False, "error": "Either message_index or message_timestamp required", "status_code": 400}

            # Get the message to delete
            target_message = messages[target_idx]

            # Auto-determine delete_next if not explicitly set
            # If deleting a user message, automatically delete the AI response
            if delete_next is None:
                delete_next = (target_message.get('type') == 'human')
                if delete_next:
                    print(f"🔄 Auto-deleting AI response for user message")

            # Delete the target message
            delete_single_message(user_id, msg_id, message_timestamp)
            deleted_count = 1

            # Delete next message if it's an AI message and delete_next is True
            if delete_next and target_idx + 1 < len(messages):
                next_msg = messages[target_idx + 1]
                if next_msg.get('type') == 'ai':
                    next_timestamp = next_msg.get('timestamp')
                    delete_single_message(user_id, msg_id, next_timestamp)
                    deleted_count = 2
                    print(f"✅ Also deleted AI response at {next_timestamp}")

            print(f"✅ Deleted {deleted_count} message(s) from new table (Cost: {deleted_count} WCUs)")

            # Check if there are any remaining messages
            remaining_messages_count = len(messages) - deleted_count
            chat_deleted = False

            if remaining_messages_count == 0:
                print(f"⚠️  No messages remain, deleting entire chat session...")
                try:
                    delete_result = delete_chat_session(user_id, msg_id)
                    if delete_result.get('success'):
                        print(f"✅ Chat session deleted successfully")
                        chat_deleted = True
                    else:
                        print(f"⚠️  Failed to delete chat session: {delete_result.get('error')}")
                except Exception as e:
                    print(f"⚠️  Error deleting chat session: {str(e)}")
                    # Don't fail the whole operation if chat deletion fails

            return {
                "success": True,
                "message": "Message(s) deleted successfully",
                "deleted_count": deleted_count,
                "chat_deleted": chat_deleted,
                "remaining_messages": remaining_messages_count
            }

        except Exception as e:
            print(f"Error deleting message from new table: {str(e)}")
            raise

    else:
        # Use old approach: read-modify-write entire history
        print("📦 Using old approach for delete (read entire history)")

        try:
            client = boto3.client('dynamodb')
            pk = generate_user_pk(user_id)
            sk = generate_history_sk(msg_id)

            # Get existing chat history
            try:
                response = client.get_item(
                    TableName="ChatMetadata",
                    Key={'PK': {'S': pk}, 'SK': {'S': sk}}
                )

                if 'Item' not in response:
                    return {"success": False, "error": "Chat history not found", "status_code": 404}

                # Extract and parse chat history
                history_data = response['Item'].get('ChatHistory', {'S': '[]'})['S']
                encrypted_history = json.loads(history_data)
                # Decrypt the chat history
                chat_history = encryption.decrypt_chat_history(encrypted_history)

            except Exception as e:
                print(f"Error retrieving chat history: {str(e)}")
                return {"success": False, "error": "Failed to retrieve chat history", "status_code": 500}

            # Validate message index
            if message_index is None:
                return {"success": False, "error": "message_index required for old table", "status_code": 400}

            if message_index >= len(chat_history):
                return {"success": False, "error": "Message index out of range", "status_code": 400}

            # Get the message to delete
            target_message = chat_history[message_index]

            # Auto-determine delete_next if not explicitly set
            # If deleting a user message, automatically delete the AI response
            if delete_next is None:
                delete_next = (target_message.get('type') == 'human')
                if delete_next:
                    print(f"🔄 Auto-deleting AI response for user message")

            # Create new list without the deleted message(s)
            new_messages = []
            for i, message in enumerate(chat_history):
                # Skip the message to delete
                if i == message_index:
                    print(f"Deleting message at index {i}: {message}")
                    continue
                # Skip the next message if delete_next is True and it's an AI message
                if delete_next and i == message_index + 1:
                    next_message = chat_history[i] if i < len(chat_history) else None
                    if next_message and next_message.get("type") == "ai":
                        print(f"✅ Also deleting AI response at index {i}: {next_message}")
                        continue
                new_messages.append(message)

            # Encrypt messages before storing
            encrypted_new_messages = encryption.encrypt_chat_history(new_messages)

            # Update the chat history in DynamoDB
            client.put_item(
                TableName="ChatMetadata",
                Item={
                    'PK': {'S': pk},
                    'SK': {'S': sk},
                    'ChatHistory': {'S': json.dumps(encrypted_new_messages)},
                    'entity_type': {'S': 'chat_history'},
                    'updated_at': {'S': datetime.now().isoformat()}
                }
            )

            deleted_count = len(chat_history) - len(new_messages)
            print(f"✅ Deleted from old table. Original: {len(chat_history)}, New: {len(new_messages)} (Cost: {len(encrypted_new_messages)} WCUs)")

            # Check if there are any remaining messages
            remaining_messages_count = len(new_messages)
            chat_deleted = False

            if remaining_messages_count == 0:
                print(f"⚠️  No messages remain, deleting entire chat session...")
                try:
                    delete_result = delete_chat_session(user_id, msg_id)
                    if delete_result.get('success'):
                        print(f"✅ Chat session deleted successfully")
                        chat_deleted = True
                    else:
                        print(f"⚠️  Failed to delete chat session: {delete_result.get('error')}")
                except Exception as e:
                    print(f"⚠️  Error deleting chat session: {str(e)}")
                    # Don't fail the whole operation if chat deletion fails

            return {
                "success": True,
                "message": "Message(s) deleted successfully",
                "deleted_count": deleted_count,
                "chat_deleted": chat_deleted,
                "remaining_messages": remaining_messages_count
            }

        except Exception as e:
            print(f"Error deleting message: {str(e)}")
            raise


def edit_message_and_regenerate(user_id: str, msg_id: str, message_index: int = None, message_timestamp: str = None, new_content: str = None, query_fn = None) -> dict:
    """
    Edit a user message and generate a new AI response

    Args:
        user_id: User ID who owns the chat
        msg_id: Message/session ID
        message_index: 0-based index of message to edit (used with old table)
        message_timestamp: ISO8601 timestamp of message to edit (used with new table)
        new_content: New content for the message
        query_fn: Function to call for generating AI response

    Returns:
        Dictionary with success status and new AI response
    """
    from core.aws.dynamodb_service import generate_user_pk, generate_history_sk

    # If new message table is enabled, use targeted update
    if use_new_message_table():
        print("🆕 Using new message-based table for edit (Cost: 2 WCUs)")

        try:
            # Get all messages to find the one to edit
            messages = get_messages_for_session(user_id, msg_id)

            if message_timestamp:
                # Find message by timestamp
                target_idx = None
                for i, msg in enumerate(messages):
                    if msg.get('timestamp') == message_timestamp:
                        target_idx = i
                        break

                if target_idx is None:
                    return {"success": False, "error": "Message not found", "status_code": 404}

            elif message_index is not None:
                # Use index to find message
                if message_index >= len(messages):
                    return {"success": False, "error": "Message index out of range", "status_code": 400}
                target_idx = message_index
                message_timestamp = messages[target_idx].get('timestamp')
            else:
                return {"success": False, "error": "Either message_index or message_timestamp required", "status_code": 400}

            # Validate it's a human message
            if messages[target_idx].get("type") != "human":
                return {"success": False, "error": "Can only edit user messages", "status_code": 400}

            # Update the user message
            print(f"✅ Updated message at {message_timestamp}")
            update_single_message(user_id, msg_id, message_timestamp, new_content)

            # Generate new AI response
            try:
                print(f"🤖 Calling query_fn to generate new AI response for: {new_content[:100]}...")
                answer = query_fn(new_content)
                print(f"📥 Received raw answer from query_fn (type: {type(answer)})")
                print(f"📥 Raw answer preview: {str(answer)[:200]}")

                # Parse the response
                if isinstance(answer, str):
                    print(f"🔍 Answer is string, checking if it's JSON...")
                    if answer.strip() and (answer.strip().startswith('{') or answer.strip().startswith('[')):
                        print(f"🔍 Attempting to parse as JSON...")
                        try:
                            new_ai_response = json.loads(answer)
                            print(f"✅ Parsed as JSON successfully")
                        except json.JSONDecodeError as je:
                            print(f"❌ JSON parse failed: {str(je)}")
                            print(f"❌ Answer content: {answer}")
                            raise
                    else:
                        print(f"✅ Answer is plain text, using directly")
                        new_ai_response = answer
                else:
                    print(f"✅ Answer is already parsed (type: {type(answer)})")
                    new_ai_response = answer

                # Extract the actual response text
                if isinstance(new_ai_response, dict):
                    print(f"🔍 Response is dict with keys: {new_ai_response.keys()}")
                    if "body" in new_ai_response:
                        print(f"🔍 Extracting from 'body' field")
                        new_ai_response = new_ai_response["body"]["answer"]
                    elif "answer" in new_ai_response:
                        print(f"🔍 Extracting from 'answer' field")
                        new_ai_response = new_ai_response["answer"]

                print(f"✅ Final AI response (type: {type(new_ai_response)}): {str(new_ai_response)[:200]}")

                # Check if there's an AI response after this message
                if target_idx + 1 < len(messages) and messages[target_idx + 1].get("type") == "ai":
                    # Update existing AI response
                    ai_timestamp = messages[target_idx + 1].get('timestamp')
                    update_single_message(user_id, msg_id, ai_timestamp, new_ai_response)
                    print(f"✅ Updated existing AI response at {ai_timestamp}")
                else:
                    # Add new AI response
                    save_individual_message(
                        user_id=user_id,
                        session_id=msg_id,
                        message_type='ai',
                        content=new_ai_response
                    )
                    print(f"✅ Added new AI response")

            except Exception as e:
                print(f"❌ Error generating new AI response: {str(e)}")
                print(f"❌ Exception type: {type(e).__name__}")
                print(f"❌ Exception args: {e.args}")
                import traceback
                print(f"❌ Full traceback:\n{traceback.format_exc()}")
                return {"success": False, "error": f"Failed to generate new response: {str(e)}", "status_code": 500}

            print(f"✅ Edited message and updated AI response (Cost: 2 WCUs)")
            return {
                "success": True,
                "message": "Message edited and new response generated",
                "new_ai_response": new_ai_response
            }

        except Exception as e:
            print(f"Error editing message in new table: {str(e)}")
            raise

    else:
        # Use old approach: read-modify-write entire history
        print("📦 Using old approach for edit (read entire history)")

        try:
            client = boto3.client('dynamodb')
            pk = generate_user_pk(user_id)
            sk = generate_history_sk(msg_id)

            # Get existing chat history
            try:
                response = client.get_item(
                    TableName="ChatMetadata",
                    Key={'PK': {'S': pk}, 'SK': {'S': sk}}
                )

                if 'Item' not in response:
                    return {"success": False, "error": "Chat history not found", "status_code": 404}

                # Extract and parse chat history
                history_data = response['Item'].get('ChatHistory', {'S': '[]'})['S']
                encrypted_history = json.loads(history_data)
                # Decrypt the chat history
                chat_history = encryption.decrypt_chat_history(encrypted_history)

            except Exception as e:
                print(f"Error retrieving chat history: {str(e)}")
                return {"success": False, "error": "Failed to retrieve chat history", "status_code": 500}

            # Validate message index
            if message_index is None:
                return {"success": False, "error": "message_index required for old table", "status_code": 400}

            if message_index >= len(chat_history):
                return {"success": False, "error": "Message index out of range", "status_code": 400}

            # Update the user message
            if chat_history[message_index].get("type") != "human":
                return {"success": False, "error": "Can only edit user messages", "status_code": 400}

            chat_history[message_index]["content"] = new_content

            # Generate new AI response
            try:
                answer = query_fn(new_content)
                new_ai_response = json.loads(answer) if isinstance(answer, str) else answer
                new_ai_response = new_ai_response["body"]["answer"] if "body" in new_ai_response else answer

                # Update or add AI response
                if message_index + 1 < len(chat_history) and chat_history[message_index + 1].get("type") == "ai":
                    # Update existing AI response
                    chat_history[message_index + 1]["content"] = new_ai_response
                else:
                    # Add new AI response
                    chat_history.insert(message_index + 1, {
                        "type": "ai",
                        "content": new_ai_response
                    })

            except Exception as e:
                print(f"Error generating new AI response: {str(e)}")
                return {"success": False, "error": "Failed to generate new response", "status_code": 500}

            # Encrypt chat history before storing
            encrypted_history = encryption.encrypt_chat_history(chat_history)

            # Update the chat history in DynamoDB
            client.put_item(
                TableName="ChatMetadata",
                Item={
                    'PK': {'S': pk},
                    'SK': {'S': sk},
                    'ChatHistory': {'S': json.dumps(encrypted_history)},
                    'entity_type': {'S': 'chat_history'},
                    'updated_at': {'S': datetime.now().isoformat()}
                }
            )

            print(f"✅ Edited message in old table (Cost: {len(encrypted_history)} WCUs)")
            return {
                "success": True,
                "message": "Message edited and new response generated",
                "new_ai_response": new_ai_response
            }

        except Exception as e:
            print(f"Error editing message: {str(e)}")
            raise


def get_chat_list(user_id: str) -> list:
    """
    Get list of all chat sessions for a user with metadata

    Args:
        user_id: User ID to fetch chats for

    Returns:
        List of chat dictionaries with session_id, chat_name, and timestamps
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('ChatMetadata')

        # Query all chat metadata for this user
        response = table.query(
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk_prefix)',
            ExpressionAttributeValues={
                ':pk': get_chat_pk(user_id),
                ':sk_prefix': 'CHAT#'
            }
        )

        chats = []
        for item in response.get('Items', []):
            # Decrypt chat name if encrypted
            chat_name = item.get('chat_name', 'Untitled Chat')
            try:
                chat_name = encryption.decrypt_chat_name(chat_name)
            except Exception:
                # If decryption fails, use as-is (might be unencrypted legacy data)
                pass

            # Extract session_id from SK (format: CHAT#{session_id})
            session_id = item.get('SK', '').replace('CHAT#', '')

            chats.append({
                'session_id': session_id,
                'chat_name': chat_name,
                'created_at': item.get('created_at', ''),
                'updated_at': item.get('updated_at', ''),
                'model_id': item.get('model_id', '')
            })

        # Sort by updated_at (most recent first)
        chats.sort(key=lambda x: x.get('updated_at', ''), reverse=True)

        return chats

    except Exception as e:
        print(f"Error fetching chat list: {str(e)}")
        return []
