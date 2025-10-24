# Chat History Migration Guide

## Overview

This guide explains the migration from the old "single-item-per-session" approach to the new **"one-item-per-message"** architecture for DynamoDB chat history storage.

## Why Migrate?

### Problems with Old Approach

The old approach stored entire chat histories as single DynamoDB items:

- **PK**: `USER#{user_id}`
- **SK**: `HISTORY#{session_id}`
- **Data**: JSON array with all messages encrypted as one blob

#### Issues:

1. **High Cost**: Every edit/delete operation requires reading and writing the **entire history**
   - Example: Deleting a 50-byte message from a 500KB history costs **500 WCUs** (Write Capacity Units)

2. **Hard 400KB Limit**: DynamoDB items cannot exceed 400KB
   - Your application will break when any user's chat history grows beyond this

3. **Poor Performance**: Reading/writing hundreds of KB for single message operations

### New Architecture Benefits

The new approach stores **each message as its own DynamoDB item**:

- **PK**: `USER#{user_id}#SESSION#{session_id}` (groups all messages for a session)
- **SK**: `MSG#{ISO8601_timestamp}` (chronologically sorted)
- **Data**: Single encrypted message

#### Benefits:

1. **Dramatically Lower Cost**:
   - Add message: 1 WCU (vs 100s in old approach)
   - Delete message: 1 WCU (vs 100s)
   - Edit message: 1-2 WCUs (vs 100s)

2. **No Size Limit**: Can scale to millions of messages per session

3. **Better Performance**: Only read/write what you need

4. **Efficient Queries**: Can fetch only recent N messages

## Migration Process

### Phase 1: Enable New Table (Zero Downtime)

1. **Update Environment Variables**

   Add to your `.env` file:
   ```bash
   USE_NEW_MESSAGE_TABLE=true
   ```

2. **Restart Server**

   The server will automatically:
   - Create the `ChatMessages` table
   - Start writing new messages to both old and new tables
   - Read from new table with fallback to old table

3. **Verify New Messages Work**

   - Create a new chat
   - Send messages
   - Try edit/delete operations
   - Check that messages appear correctly

### Phase 2: Migrate Existing Data

Run the migration script to copy existing chat histories:

```bash
cd /path/to/server

# Step 1: Dry run first (see what will be migrated)
python migrations/migrate.py --all --dry-run

# Step 2: Run actual migration
python migrations/migrate.py --all
```

**Requirements:**
- `boto3`, `cryptography`, `python-dotenv` installed
- `CHAT_ENCRYPTION_KEY` set in `.env`
- AWS credentials configured

**Expected Output:**

```
================================================================================
🔄 CHAT HISTORY MIGRATION SCRIPT
================================================================================
This script migrates chat history from the old format (one item per session)
to the new format (one item per message) for better scalability.
================================================================================

🔍 Scanning ChatSessions table for all history items...
✅ Found 25 sessions to migrate

📦 Migrating session: abc123 for user: user_456
   Reading from: PK=USER#user_456, SK=HISTORY#abc123
   ✅ Found 42 messages (per-message encryption)
   ✅ Migrated 42/42 messages to new table

... (continues for all sessions) ...

================================================================================
📊 MIGRATION SUMMARY
================================================================================
Total sessions: 25
✅ Successful: 25
❌ Failed: 0
📝 Total messages: 1,247

✅ Migration complete!

Next steps:
1. Set USE_NEW_MESSAGE_TABLE=true in your .env file
2. Restart your server
3. Verify that messages are loading correctly
4. (Optional) After confirming everything works, you can delete old history items
================================================================================
```

### Phase 3: Verify Migration

1. **Test Old Sessions**

   - Open chats that existed before migration
   - Verify all messages appear correctly
   - Try edit/delete operations
   - Check that images still load

2. **Monitor Server Logs**

   Look for these indicators:
   ```
   🆕 Using new message-based table (one item per message)
   ✅ Retrieved 42 messages for session abc123
   ✅ Deleted 1 message(s) from new table (Cost: 1 WCUs)
   ```

3. **Check DynamoDB Console**

   - Go to AWS Console → DynamoDB → `ChatMessages` table
   - Verify items exist with PK pattern: `USER#{user_id}#SESSION#{session_id}`
   - Verify SK pattern: `MSG#{timestamp}`

## Cost Comparison

### Old Approach (Read-Modify-Write)

| Operation | Chat with 100 messages (≈50KB) | Chat with 1000 messages (≈500KB) |
|-----------|-------------------------------|----------------------------------|
| Add message | ~50 WCUs | ~500 WCUs |
| Delete message | ~50 WCUs | ~500 WCUs |
| Edit message | ~50 WCUs | ~500 WCUs |
| Retrieve history | ~13 RCUs | ~125 RCUs |

### New Approach (One Item Per Message)

| Operation | Any chat size |
|-----------|--------------|
| Add message | **1 WCU** |
| Delete message | **1 WCU** |
| Edit message | **2 WCUs** |
| Retrieve history | **1-25 RCUs** (can limit to recent messages) |

### Example Savings

For a user who edits 10 messages in a 500KB chat:

- **Old approach**: 10 × 500 = **5,000 WCUs**
- **New approach**: 10 × 2 = **20 WCUs**
- **Savings**: **99.6%** reduction in write costs

## Architecture Details

### Data Model

#### Old Table (ChatSessions - History Items)

```json
{
  "PK": "USER#user_123",
  "SK": "HISTORY#session_456",
  "entity_type": "chat_history",
  "ChatHistory": "[{encrypted message 1}, {encrypted message 2}, ...]"
}
```

#### New Table (ChatMessages)

```json
// Message 1
{
  "PK": "USER#user_123#SESSION#session_456",
  "SK": "MSG#2025-10-24T12:30:05.123",
  "entity_type": "message",
  "type": "human",
  "content": "encrypted_content_here",
  "encrypted": true,
  "created_at": "2025-10-24T12:30:05.123"
}

// Message 2
{
  "PK": "USER#user_123#SESSION#session_456",
  "SK": "MSG#2025-10-24T12:30:07.456",
  "entity_type": "message",
  "type": "ai",
  "content": "encrypted_content_here",
  "encrypted": true,
  "created_at": "2025-10-24T12:30:07.456"
}
```

### API Changes

The following endpoints now support both `message_index` (old) and `message_timestamp` (new):

#### Delete Message

**Old Format:**
```json
POST /delete_message
{
  "msg_id": "session_456",
  "message_index": 5,
  "delete_next": true
}
```

**New Format (Recommended):**
```json
POST /delete_message
{
  "msg_id": "session_456",
  "message_timestamp": "2025-10-24T12:30:05.123",
  "delete_next": true
}
```

#### Edit Message

**Old Format:**
```json
POST /edit_message
{
  "msg_id": "session_456",
  "message_index": 5,
  "new_content": "Updated message"
}
```

**New Format (Recommended):**
```json
POST /edit_message
{
  "msg_id": "session_456",
  "message_timestamp": "2025-10-24T12:30:05.123",
  "new_content": "Updated message"
}
```

#### Retrieve Messages

Now includes `timestamp` in response when using new table:

```json
{
  "msgs": [
    {
      "role": "human",
      "msg": "Hello",
      "timestamp": "2025-10-24T12:30:05.123"
    },
    {
      "role": "ai",
      "msg": "Hi there!",
      "timestamp": "2025-10-24T12:30:07.456"
    }
  ]
}
```

## Rollback Plan

If you need to rollback:

1. **Set Environment Variable**
   ```bash
   USE_NEW_MESSAGE_TABLE=false
   ```

2. **Restart Server**

3. **Server will revert to old table**
   - Reads from `ChatSessions` HISTORY items
   - Writes to `ChatSessions` HISTORY items
   - New table is ignored

**Note**: Any messages created while `USE_NEW_MESSAGE_TABLE=true` will not be visible after rollback unless you migrate them back to the old format.

## Cleanup (Optional)

After confirming the new system works for 1-2 weeks:

### Delete Old History Items

```python
# Run this script to delete old history items (keep metadata)
import boto3

client = boto3.client('dynamodb')
paginator = client.get_paginator('scan')

page_iterator = paginator.paginate(
    TableName='ChatSessions',
    FilterExpression='entity_type = :type',
    ExpressionAttributeValues={':type': {'S': 'chat_history'}}
)

for page in page_iterator:
    for item in page['Items']:
        pk = item['PK']['S']
        sk = item['SK']['S']
        client.delete_item(
            TableName='ChatSessions',
            Key={'PK': {'S': pk}, 'SK': {'S': sk}}
        )
        print(f"Deleted: {pk} / {sk}")

print("Cleanup complete!")
```

**Warning**: Only run this after verifying the new system works perfectly!

## Troubleshooting

### Messages Not Loading

**Symptoms**: Chat history appears empty or some messages are missing

**Solution**:
1. Check server logs for errors
2. Verify `USE_NEW_MESSAGE_TABLE` environment variable
3. Check if migration completed successfully
4. Verify encryption key hasn't changed

### High Write Costs Continue

**Symptoms**: DynamoDB costs remain high after migration

**Solution**:
1. Verify `USE_NEW_MESSAGE_TABLE=true` in .env
2. Check server logs - should see "Using new message-based table"
3. If logs show "Using old approach", restart server

### Migration Script Fails

**Symptoms**: Migration script errors or stops partway through

**Solution**:
1. Check AWS credentials have DynamoDB permissions
2. Verify encryption key is set correctly
3. Run with `--dry-run` first to identify issues
4. Migrate one user at a time if needed

### Timestamps Not Appearing in Frontend

**Symptoms**: Edit/delete operations fail, saying timestamp is required

**Solution**:
1. Frontend needs to be updated to send `message_timestamp` instead of `message_index`
2. The `/retrieve_messages` endpoint now includes timestamps - update frontend to capture them
3. For backward compatibility, `message_index` still works

## Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `USE_NEW_MESSAGE_TABLE` | `true` / `false` | `false` | Enable new message-based architecture |
| `CHAT_ENCRYPTION_KEY` | Any string | Generated | Must be consistent across restarts |

## Support

For issues or questions:
1. Check server logs for detailed error messages
2. Verify AWS DynamoDB table exists and has correct schema
3. Test with a single user/session first before migrating all data
4. Keep old data for at least 2 weeks before cleanup

## Summary

✅ **Scalability**: No more 400KB limit
✅ **Cost**: 99%+ reduction in write costs
✅ **Performance**: Only read/write what you need
✅ **Backward Compatible**: Old table still works
✅ **Zero Downtime**: Migrate without service interruption
