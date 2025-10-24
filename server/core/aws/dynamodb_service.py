"""
DynamoDB service for chat session and message management

This module supports both:
1. Old approach: Entire chat history in one item (legacy)
2. New approach: One item per message (recommended)
"""
import json
import boto3
import os
from datetime import datetime
from core.services.encryption import encryption


def generate_user_pk(user_id: str) -> str:
    """Generate partition key for user-based queries"""
    return f"USER#{user_id}"


def generate_history_sk(session_id: str) -> str:
    """Generate sort key for chat history records"""
    return f"HISTORY#{session_id}"


def get_chat_pk(user_id: str) -> str:
    """Generate partition key for user chats"""
    return f"USER#{user_id}"


def get_chat_sk(session_id: str) -> str:
    """Generate sort key for chat metadata"""
    return f"CHAT#{session_id}"


def get_history_pk(session_id: str) -> str:
    """Generate partition key for chat history"""
    return f"CHAT#{session_id}"


def get_current_timestamp() -> str:
    """Get current ISO timestamp"""
    return datetime.now().isoformat() + "Z"


def validate_user_access(authenticated_user_id: str) -> bool:
    """Validate that the authenticated user is allowed to access resources"""
    if not authenticated_user_id or authenticated_user_id.strip() == "":
        return False
    return True


def save_chat_message_to_dynamodb(user_id: str, msg_id: str, question: str, answer: str, image_urls: list = None):
    """Helper to save streamed conversation to DynamoDB"""
    try:
        client = boto3.client('dynamodb')
        pk = generate_user_pk(user_id)
        sk = generate_history_sk(msg_id)

        # Get existing chat history
        response = client.get_item(
            TableName="ChatSessions",
            Key={'PK': {'S': pk}, 'SK': {'S': sk}}
        )

        # Build new message entry (use 'type' and 'content' to match update_chat_history format)
        new_message = {
            "type": "human",
            "content": question
        }

        if image_urls:
            new_message["image_urls"] = image_urls

        new_response = {
            "type": "ai",
            "content": answer
        }

        # Append to existing messages or create new
        if 'Item' in response and 'ChatHistory' in response['Item']:
            # Changed from 'messages' to 'ChatHistory'
            encrypted_history = json.loads(response['Item']['ChatHistory']['S'])
            # Decrypt the chat history using encrypt_chat_history (matches update_chat_history)
            try:
                existing_messages = encryption.decrypt_chat_history(encrypted_history)
            except Exception as decrypt_error:
                print(f"⚠️ Decryption failed, starting fresh: {decrypt_error}")
                existing_messages = []

            existing_messages.append(new_message)
            existing_messages.append(new_response)
            messages = existing_messages
        else:
            messages = [new_message, new_response]

        # Encrypt and save (use encrypt_chat_history to match update_chat_history)
        encrypted_messages = encryption.encrypt_chat_history(messages)

        client.put_item(
            TableName="ChatSessions",
            Item={
                'PK': {'S': pk},
                'SK': {'S': sk},
                'ChatHistory': {'S': json.dumps(encrypted_messages)},  # Changed from 'messages' to 'ChatHistory'
                'entity_type': {'S': 'chat_history'},
                'updated_at': {'S': datetime.now().isoformat()}
            }
        )
        print(f"✅ Saved message to DynamoDB")
    except Exception as e:
        print(f"⚠️ Failed to save to DynamoDB: {e}")


def use_new_message_table() -> bool:
    """
    Check if we should use the new message-based table

    Returns True if USE_NEW_MESSAGE_TABLE environment variable is set to 'true'
    Default is False to maintain backward compatibility
    """
    return os.getenv('USE_NEW_MESSAGE_TABLE', 'false').lower() == 'true'


def ensure_chat_sessions_table_exists():
    """Ensure the ChatSessions DynamoDB table exists"""
    try:
        dynamodb = boto3.client('dynamodb')

        try:
            dynamodb.describe_table(TableName='ChatSessions')
            print("✅ ChatSessions table exists")
        except dynamodb.exceptions.ResourceNotFoundException:
            print("⚠️ ChatSessions table not found, creating...")

            dynamodb.create_table(
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
            waiter = dynamodb.get_waiter('table_exists')
            waiter.wait(TableName='ChatSessions')
            print("✅ ChatSessions table created successfully")

    except Exception as e:
        print(f"❌ Error ensuring ChatSessions table exists: {str(e)}")
        raise


def ensure_all_tables_exist():
    """
    Ensure both ChatSessions and ChatMessages tables exist

    This function should be called on server startup
    """
    try:
        # Ensure ChatSessions table exists (for metadata)
        ensure_chat_sessions_table_exists()

        # Ensure ChatMessages table exists (for individual messages)
        from core.aws.dynamodb_messages_service import ensure_chat_messages_table_exists
        ensure_chat_messages_table_exists()

        print("✅ All DynamoDB tables are ready")
        return True

    except Exception as e:
        print(f"❌ Error ensuring tables exist: {str(e)}")
        return False
