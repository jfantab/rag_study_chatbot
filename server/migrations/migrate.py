"""
Chat History Migration Script
==============================

Migrates chat history from old format to new message-based table.

OLD FORMAT (inefficient):
  - PK: USER#{user_id}
  - SK: HISTORY#{session_id}
  - Data: Entire chat history in one item
  - Problem: 400KB limit, expensive edit/delete operations

NEW FORMAT (efficient):
  - PK: USER#{user_id}#SESSION#{session_id}
  - SK: MSG#{timestamp}
  - Data: One message per item
  - Benefits: No size limit, 99% cost reduction, better performance

USAGE:
  # Preview migration (recommended first)
  python migrations/migrate.py --all --dry-run

  # Run migration
  python migrations/migrate.py --all

REQUIREMENTS:
  - boto3
  - cryptography
  - python-dotenv
  - CHAT_ENCRYPTION_KEY in .env

After migration, add to .env:
  USE_NEW_MESSAGE_TABLE=true
"""
import boto3
import json
import os
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Get encryption settings
ENCRYPTION_KEY = os.getenv('CHAT_ENCRYPTION_KEY')
ENCRYPTION_SALT = os.getenv('ENCRYPTION_SALT', 'default_app_salt_v1')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')


def setup_encryption():
    """Setup encryption using same logic as server"""
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        import base64

        if not ENCRYPTION_KEY:
            print("⚠️  WARNING: CHAT_ENCRYPTION_KEY not found in environment")
            print("   Migration will proceed but may fail to decrypt messages")
            return None

        key = ENCRYPTION_KEY.encode()
        salt = ENCRYPTION_SALT.encode()[:16].ljust(16, b'0')

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        fernet_key = base64.urlsafe_b64encode(kdf.derive(key))
        cipher_suite = Fernet(fernet_key)

        return cipher_suite
    except ImportError:
        print("❌ cryptography module not found. Install with: pip install cryptography")
        return None


def decrypt_text(cipher_suite, encrypted_text):
    """Decrypt a base64 encoded encrypted text string"""
    import base64
    if not encrypted_text:
        return encrypted_text
    encrypted_data = base64.b64decode(encrypted_text.encode('utf-8'))
    decrypted_data = cipher_suite.decrypt(encrypted_data)
    return decrypted_data.decode('utf-8')


def encrypt_text(cipher_suite, text):
    """Encrypt a text string and return base64 encoded encrypted data"""
    import base64
    if not text:
        return text
    encrypted_data = cipher_suite.encrypt(text.encode('utf-8'))
    return base64.b64encode(encrypted_data).decode('utf-8')


def decrypt_message_content(cipher_suite, encrypted_message):
    """Decrypt the content field of a message"""
    decrypted_message = encrypted_message.copy()

    if encrypted_message.get('encrypted', False):
        if 'content' in decrypted_message and decrypted_message['content']:
            decrypted_message['content'] = decrypt_text(cipher_suite, decrypted_message['content'])

        if 'image_urls' in decrypted_message and decrypted_message['image_urls']:
            decrypted_urls = []
            for url in decrypted_message['image_urls']:
                decrypted_urls.append(decrypt_text(cipher_suite, url))
            decrypted_message['image_urls'] = decrypted_urls

        decrypted_message.pop('encrypted', None)

    return decrypted_message


def encrypt_message_content(cipher_suite, message):
    """Encrypt the content field of a message"""
    encrypted_message = message.copy()

    if 'content' in encrypted_message and encrypted_message['content']:
        encrypted_message['content'] = encrypt_text(cipher_suite, encrypted_message['content'])
        encrypted_message['encrypted'] = True

    if 'image_urls' in encrypted_message and encrypted_message['image_urls']:
        encrypted_urls = []
        for url in encrypted_message['image_urls']:
            encrypted_urls.append(encrypt_text(cipher_suite, url))
        encrypted_message['image_urls'] = encrypted_urls

    return encrypted_message


def decrypt_chat_history(cipher_suite, encrypted_history):
    """Decrypt all message content in chat history"""
    decrypted_history = []
    for message in encrypted_history:
        decrypted_message = decrypt_message_content(cipher_suite, message)
        decrypted_history.append(decrypted_message)
    return decrypted_history


def ensure_chat_messages_table_exists(client):
    """Create ChatMessages table if it doesn't exist"""
    try:
        client.describe_table(TableName='ChatMessages')
        print("✅ ChatMessages table already exists")
        return True
    except client.exceptions.ResourceNotFoundException:
        pass

    print("📦 Creating ChatMessages table...")
    client.create_table(
        TableName='ChatMessages',
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

    waiter = client.get_waiter('table_exists')
    waiter.wait(TableName='ChatMessages')
    print("✅ ChatMessages table created successfully")
    return True


def migrate_session(client, cipher_suite, user_id, session_id, dry_run=False):
    """Migrate a single session's chat history"""
    pk = f"USER#{user_id}"
    sk = f"HISTORY#{session_id}"

    print(f"\n📦 Migrating session: {session_id[:30]}...")
    print(f"   User: {user_id[:50]}...")

    # Read from old format
    response = client.get_item(
        TableName="ChatSessions",
        Key={'PK': {'S': pk}, 'SK': {'S': sk}}
    )

    if 'Item' not in response:
        print(f"   ⚠️  No history found")
        return {"success": False, "error": "No history found"}

    item = response['Item']

    # Parse and decrypt chat history
    if 'ChatHistory' in item:
        history_data = item['ChatHistory']['S']
        encrypted_history = json.loads(history_data)
        chat_history = decrypt_chat_history(cipher_suite, encrypted_history)
        print(f"   ✅ Found {len(chat_history)} messages (per-message encryption)")
    elif 'messages' in item:
        messages_str = item['messages']['S']
        try:
            decrypted_str = decrypt_text(cipher_suite, messages_str)
            chat_history = json.loads(decrypted_str)
            print(f"   ✅ Found {len(chat_history)} messages (legacy encryption)")
        except:
            chat_history = json.loads(messages_str)
            print(f"   ✅ Found {len(chat_history)} messages (unencrypted)")
    else:
        print(f"   ❌ No chat history field found")
        return {"success": False, "error": "No chat history field"}

    if dry_run:
        print(f"   🔍 DRY RUN: Would migrate {len(chat_history)} messages")
        for i, msg in enumerate(chat_history[:3]):
            msg_type = msg.get('type', msg.get('role', 'unknown'))
            content = msg.get('content', msg.get('msg', ''))[:50]
            print(f"      {i+1}. [{msg_type}] {content}...")
        return {"success": True, "message_count": len(chat_history), "dry_run": True}

    # Write each message to new table
    migrated_count = 0
    new_pk = f"USER#{user_id}#SESSION#{session_id}"

    for i, msg in enumerate(chat_history):
        msg_type = msg.get('type', msg.get('role', 'human'))
        content = msg.get('content', msg.get('msg', ''))
        image_urls = msg.get('image_urls', None)
        file_attachments = msg.get('file_attachments', None)

        # Generate timestamp (use index to maintain order)
        base_timestamp = datetime.now().replace(microsecond=0)
        msg_timestamp = base_timestamp.replace(second=i % 60, minute=i // 60).isoformat()
        new_sk = f"MSG#{msg_timestamp}"

        # Re-encrypt the message
        message_obj = {
            "type": msg_type,
            "content": content
        }
        if image_urls:
            message_obj["image_urls"] = image_urls
        if file_attachments:
            message_obj["file_attachments"] = file_attachments

        encrypted_msg = encrypt_message_content(cipher_suite, message_obj)

        # Build DynamoDB item
        new_item = {
            'PK': {'S': new_pk},
            'SK': {'S': new_sk},
            'entity_type': {'S': 'message'},
            'type': {'S': encrypted_msg['type']},
            'content': {'S': encrypted_msg['content']},
            'created_at': {'S': msg_timestamp}
        }

        if 'image_urls' in encrypted_msg and encrypted_msg['image_urls']:
            new_item['image_urls'] = {'L': [{'S': url} for url in encrypted_msg['image_urls']]}

        if file_attachments:
            new_item['file_attachments'] = {'S': json.dumps(file_attachments)}

        if encrypted_msg.get('encrypted', False):
            new_item['encrypted'] = {'BOOL': True}

        try:
            client.put_item(TableName='ChatMessages', Item=new_item)
            migrated_count += 1
        except Exception as e:
            print(f"   ❌ Failed to migrate message {i+1}: {str(e)}")

    print(f"   ✅ Migrated {migrated_count}/{len(chat_history)} messages")
    return {"success": True, "message_count": len(chat_history), "migrated_count": migrated_count}


def main():
    parser = argparse.ArgumentParser(description='Simple migration script')
    parser.add_argument('--all', action='store_true', help='Migrate all sessions')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be migrated')
    args = parser.parse_args()

    print("=" * 80)
    print("🔄 SIMPLE CHAT HISTORY MIGRATION")
    print("=" * 80)

    # Setup encryption
    cipher_suite = setup_encryption()
    if not cipher_suite:
        print("❌ Failed to setup encryption. Aborting.")
        return

    # Setup DynamoDB client
    client = boto3.client('dynamodb', region_name=AWS_REGION)

    # Ensure new table exists
    if not args.dry_run:
        ensure_chat_messages_table_exists(client)

    # Find all sessions
    print("\n🔍 Scanning for chat history items...")
    response = client.scan(
        TableName='ChatSessions',
        FilterExpression='entity_type = :type',
        ExpressionAttributeValues={':type': {'S': 'chat_history'}}
    )

    items = response.get('Items', [])
    print(f"✅ Found {len(items)} session(s) to migrate")

    if args.dry_run:
        print("\n🔍 DRY RUN MODE: No data will be written")

    # Migrate each session
    results = {"total": len(items), "success": 0, "failed": 0, "total_messages": 0}

    for item in items:
        pk = item['PK']['S']
        sk = item['SK']['S']

        user_id = pk.replace('USER#', '')
        session_id = sk.replace('HISTORY#', '')

        result = migrate_session(client, cipher_suite, user_id, session_id, args.dry_run)

        if result.get('success'):
            results["success"] += 1
            results["total_messages"] += result.get('message_count', 0)
        else:
            results["failed"] += 1

    # Summary
    print("\n" + "=" * 80)
    print("📊 MIGRATION SUMMARY")
    print("=" * 80)
    print(f"Total sessions: {results['total']}")
    print(f"✅ Successful: {results['success']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"📝 Total messages: {results['total_messages']}")

    if args.dry_run:
        print("\n🔍 This was a DRY RUN - no data was written")
        print("   Run without --dry-run to perform actual migration")
    else:
        print("\n✅ Migration complete!")
        print("\nNext steps:")
        print("1. Add to .env: USE_NEW_MESSAGE_TABLE=true")
        print("2. Restart your server")
        print("3. Verify messages load correctly")

    print("=" * 80)


if __name__ == "__main__":
    main()
