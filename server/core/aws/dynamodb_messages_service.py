"""
DynamoDB service for individual message management (one item per message)

This module implements the scalable one-item-per-message architecture where:
- Each message is stored as a separate DynamoDB item
- Messages are grouped by session using PK = USER#{user_id}#SESSION#{session_id}
- Messages are ordered chronologically using SK = MSG#{ISO8601_timestamp}
- Individual messages can be efficiently added, updated, or deleted (1 WCU each)
"""
import json
import boto3
from datetime import datetime
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError
from core.services.encryption import encryption


# Table name for individual messages
MESSAGES_TABLE_NAME = 'ChatMessages'


def generate_message_pk(user_id: str, session_id: str) -> str:
    """
    Generate partition key for message-based queries

    Args:
        user_id: User ID who owns the chat
        session_id: Session/chat ID

    Returns:
        Partition key in format: USER#{user_id}#SESSION#{session_id}
    """
    return f"USER#{user_id}#SESSION#{session_id}"


def generate_message_sk(timestamp: str = None) -> str:
    """
    Generate sort key for individual messages

    Args:
        timestamp: ISO8601 timestamp (optional, defaults to current time)

    Returns:
        Sort key in format: MSG#{ISO8601_timestamp}
    """
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    return f"MSG#{timestamp}"


def get_current_iso_timestamp() -> str:
    """Get current ISO8601 timestamp"""
    return datetime.now().isoformat()


def save_individual_message(
    user_id: str,
    session_id: str,
    message_type: str,
    content: str,
    image_urls: Optional[List[str]] = None,
    file_attachments: Optional[List[Dict[str, Any]]] = None,
    timestamp: Optional[str] = None,
    image_captions: Optional[List[str]] = None,
    file_summaries: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Save a single message as an individual DynamoDB item

    Args:
        user_id: User ID who owns the chat
        session_id: Session/chat ID
        message_type: Either 'human' or 'ai'
        content: Message content (will be encrypted)
        image_urls: Optional list of image URLs (will be encrypted)
        file_attachments: Optional list of file metadata
        timestamp: Optional timestamp (defaults to current time)
        image_captions: Optional list of image descriptions/captions for context
        file_summaries: Optional list of file summaries for context

    Returns:
        Dictionary with success status and message info

    Cost: 1 WCU per message (vs 100s of WCUs in old read-modify-write approach)
    """
    try:
        print(f"🔵 [SAVE_INDIVIDUAL_MESSAGE] Starting save...")
        print(f"   - user_id: {user_id}")
        print(f"   - session_id: {session_id}")
        print(f"   - message_type: {message_type}")
        print(f"   - content length: {len(content)}")
        print(f"   - image_urls: {image_urls}")
        print(f"   - file_attachments: {file_attachments}")

        client = boto3.client('dynamodb')
        print(f"✅ [SAVE_INDIVIDUAL_MESSAGE] DynamoDB client created")

        # Generate keys
        pk = generate_message_pk(user_id, session_id)
        if timestamp is None:
            timestamp = get_current_iso_timestamp()
        sk = generate_message_sk(timestamp)

        # Build message object for encryption
        message_obj = {
            "type": message_type,
            "content": content
        }

        if image_urls:
            message_obj["image_urls"] = image_urls

        if file_attachments:
            message_obj["file_attachments"] = file_attachments

        if image_captions:
            message_obj["image_captions"] = image_captions

        if file_summaries:
            message_obj["file_summaries"] = file_summaries

        # Encrypt the message content (and image URLs if present)
        encrypted_message = encryption.encrypt_message_content(message_obj)

        # Build DynamoDB item
        item = {
            'PK': {'S': pk},
            'SK': {'S': sk},
            'entity_type': {'S': 'message'},
            'type': {'S': encrypted_message['type']},
            'content': {'S': encrypted_message['content']},
            'created_at': {'S': timestamp}
        }

        # Add encrypted image URLs if present
        if 'image_urls' in encrypted_message and encrypted_message['image_urls']:
            item['image_urls'] = {'L': [{'S': url} for url in encrypted_message['image_urls']]}

        # Add encrypted file attachments if present
        if 'file_attachments' in encrypted_message and encrypted_message['file_attachments']:
            item['file_attachments'] = {'S': json.dumps(encrypted_message['file_attachments'])}

        # Add image captions if present (stored as JSON list)
        if 'image_captions' in encrypted_message and encrypted_message['image_captions']:
            item['image_captions'] = {'S': json.dumps(encrypted_message['image_captions'])}

        # Add file summaries if present (stored as JSON list)
        if 'file_summaries' in encrypted_message and encrypted_message['file_summaries']:
            item['file_summaries'] = {'S': json.dumps(encrypted_message['file_summaries'])}

        # Add encrypted flag
        if encrypted_message.get('encrypted', False):
            item['encrypted'] = {'BOOL': True}

        # Save to DynamoDB
        print(f"💾 [SAVE_INDIVIDUAL_MESSAGE] Writing to DynamoDB table: {MESSAGES_TABLE_NAME}")
        print(f"   - PK: {pk}")
        print(f"   - SK: {sk}")

        client.put_item(
            TableName=MESSAGES_TABLE_NAME,
            Item=item
        )

        print(f"✅ Saved individual message: {message_type} at {timestamp}")
        return {
            "success": True,
            "timestamp": timestamp,
            "pk": pk,
            "sk": sk
        }

    except Exception as e:
        print(f"❌ [SAVE_INDIVIDUAL_MESSAGE] Error saving individual message: {str(e)}")
        import traceback
        print(f"❌ [SAVE_INDIVIDUAL_MESSAGE] Traceback:\n{traceback.format_exc()}")
        raise


def get_messages_for_session(
    user_id: str,
    session_id: str,
    limit: Optional[int] = None,
    ascending: bool = True
) -> List[Dict[str, Any]]:
    """
    Query all messages for a chat session

    Args:
        user_id: User ID who owns the chat
        session_id: Session/chat ID
        limit: Optional limit on number of messages to retrieve
        ascending: If True, oldest first; if False, newest first

    Returns:
        List of decrypted message dictionaries

    Cost: Much more efficient than reading entire history
          Can get just last N messages instead of everything
    """
    try:
        client = boto3.client('dynamodb')
        pk = generate_message_pk(user_id, session_id)

        # Build query parameters
        query_params = {
            'TableName': MESSAGES_TABLE_NAME,
            'KeyConditionExpression': 'PK = :pk AND begins_with(SK, :sk_prefix)',
            'ExpressionAttributeValues': {
                ':pk': {'S': pk},
                ':sk_prefix': {'S': 'MSG#'}
            },
            'ScanIndexForward': ascending  # True = ascending (oldest first)
        }

        if limit:
            query_params['Limit'] = limit

        # Query DynamoDB
        response = client.query(**query_params)

        # Decrypt and format messages
        messages = []
        for item in response.get('Items', []):
            # Build message object for decryption
            message_obj = {
                'type': item['type']['S'],
                'content': item['content']['S']
            }

            # Check if message is encrypted
            if item.get('encrypted', {}).get('BOOL', False):
                message_obj['encrypted'] = True

            # Add image URLs if present
            if 'image_urls' in item:
                message_obj['image_urls'] = [url['S'] for url in item['image_urls']['L']]

            # Add file attachments if present
            if 'file_attachments' in item:
                message_obj['file_attachments'] = json.loads(item['file_attachments']['S'])

            # Add image captions if present
            if 'image_captions' in item:
                message_obj['image_captions'] = json.loads(item['image_captions']['S'])

            # Add file summaries if present
            if 'file_summaries' in item:
                message_obj['file_summaries'] = json.loads(item['file_summaries']['S'])

            # Decrypt the message
            decrypted_message = encryption.decrypt_message_content(message_obj)

            # Add timestamp for client use
            decrypted_message['timestamp'] = item['created_at']['S']

            messages.append(decrypted_message)

        print(f"✅ Retrieved {len(messages)} messages for session {session_id}")
        return messages

    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"⚠️  ChatMessages table not found, returning empty list")
            return []
        print(f"❌ Error querying messages: {str(e)}")
        raise
    except Exception as e:
        print(f"❌ Error getting messages for session: {str(e)}")
        raise


def update_single_message(
    user_id: str,
    session_id: str,
    timestamp: str,
    new_content: str
) -> Dict[str, Any]:
    """
    Update a specific message by its timestamp

    Args:
        user_id: User ID who owns the chat
        session_id: Session/chat ID
        timestamp: ISO8601 timestamp of the message to update
        new_content: New content for the message

    Returns:
        Dictionary with success status

    Cost: 1 WCU (vs 100s of WCUs in old approach)
    """
    try:
        client = boto3.client('dynamodb')

        pk = generate_message_pk(user_id, session_id)
        sk = generate_message_sk(timestamp)

        # Encrypt the new content
        encrypted_content = encryption.encrypt_text(new_content)

        # Update the item
        client.update_item(
            TableName=MESSAGES_TABLE_NAME,
            Key={
                'PK': {'S': pk},
                'SK': {'S': sk}
            },
            UpdateExpression='SET content = :c, encrypted = :enc',
            ExpressionAttributeValues={
                ':c': {'S': encrypted_content},
                ':enc': {'BOOL': True}
            }
        )

        print(f"✅ Updated message at {timestamp}")
        return {
            "success": True,
            "timestamp": timestamp
        }

    except Exception as e:
        print(f"❌ Error updating message: {str(e)}")
        raise


def delete_single_message(
    user_id: str,
    session_id: str,
    timestamp: str
) -> Dict[str, Any]:
    """
    Delete a specific message by its timestamp

    Args:
        user_id: User ID who owns the chat
        session_id: Session/chat ID
        timestamp: ISO8601 timestamp of the message to delete

    Returns:
        Dictionary with success status

    Cost: 1 WCU (vs 100s of WCUs in old approach)
    """
    try:
        client = boto3.client('dynamodb')

        pk = generate_message_pk(user_id, session_id)
        sk = generate_message_sk(timestamp)

        # Delete the item
        client.delete_item(
            TableName=MESSAGES_TABLE_NAME,
            Key={
                'PK': {'S': pk},
                'SK': {'S': sk}
            }
        )

        print(f"✅ Deleted message at {timestamp}")
        return {
            "success": True,
            "timestamp": timestamp
        }

    except Exception as e:
        print(f"❌ Error deleting message: {str(e)}")
        raise


def ensure_chat_messages_table_exists():
    """
    Create ChatMessages table if it doesn't exist

    Table schema:
    - PK: USER#{user_id}#SESSION#{session_id}
    - SK: MSG#{ISO8601_timestamp}
    - Attributes: entity_type, type, content (encrypted), image_urls (encrypted),
                  file_attachments, created_at
    """
    try:
        client = boto3.client('dynamodb')

        # Check if table exists
        try:
            client.describe_table(TableName=MESSAGES_TABLE_NAME)
            print(f"✅ {MESSAGES_TABLE_NAME} table already exists")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                raise e

        print(f"Creating {MESSAGES_TABLE_NAME} table...")

        # Create the table with same schema as ChatMetadata (PK + SK)
        client.create_table(
            TableName=MESSAGES_TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},   # Partition key
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}   # Sort key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'  # On-demand pricing
        )

        # Wait for table to be created
        waiter = client.get_waiter('table_exists')
        waiter.wait(TableName=MESSAGES_TABLE_NAME)

        print(f"✅ {MESSAGES_TABLE_NAME} table created successfully")
        return True

    except Exception as e:
        print(f"❌ Error ensuring {MESSAGES_TABLE_NAME} table exists: {str(e)}")
        return False


def get_message_count_for_session(user_id: str, session_id: str) -> int:
    """
    Get the count of messages in a session (useful for metadata updates)

    Args:
        user_id: User ID who owns the chat
        session_id: Session/chat ID

    Returns:
        Number of messages in the session
    """
    try:
        client = boto3.client('dynamodb')
        pk = generate_message_pk(user_id, session_id)

        response = client.query(
            TableName=MESSAGES_TABLE_NAME,
            KeyConditionExpression='PK = :pk AND begins_with(SK, :sk_prefix)',
            ExpressionAttributeValues={
                ':pk': {'S': pk},
                ':sk_prefix': {'S': 'MSG#'}
            },
            Select='COUNT'  # Only return count, not items
        )

        return response.get('Count', 0)

    except Exception as e:
        print(f"❌ Error getting message count: {str(e)}")
        return 0
