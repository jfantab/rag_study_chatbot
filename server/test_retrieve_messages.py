"""
Test suite for the /retrieve_messages endpoint

This test file helps debug chat history retrieval issues.
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test configuration
BASE_URL = os.getenv('TEST_BASE_URL', "https://jfantabai.xyz")
ENDPOINT = f"{BASE_URL}/retrieve_messages"

# Auth token
TEST_TOKEN = os.getenv('TEST_AUTH_TOKEN', 'your-test-token-here')

# Session IDs from the chat list
SESSION_IDS = [
    '1761807242770qgora3lbo',  # Tell me about string theory
    '1761807123351zbpgkcbm3',  # Hey
]


def test_retrieve_messages(session_id):
    """
    Test retrieving messages for a specific session
    """
    print("\n" + "="*80)
    print(f"TEST: Retrieve Messages for Session: {session_id}")
    print("="*80)

    headers = {
        'Authorization': f'Bearer {TEST_TOKEN}',
        'Content-Type': 'application/json'
    }

    params = {
        'msgId': session_id
    }

    print(f"\n🔍 Request Details:")
    print(f"   URL: {ENDPOINT}")
    print(f"   Params: {params}")
    print(f"   Token: {TEST_TOKEN[:50]}...")

    try:
        response = requests.get(ENDPOINT, headers=headers, params=params)

        print(f"\n📥 Response:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ SUCCESS: Retrieved messages")
            print(f"\nResponse Data:")
            print(json.dumps(data, indent=2))

            # Validate response structure
            assert 'msgs' in data, "Response should contain 'msgs' key"
            assert isinstance(data['msgs'], list), "'msgs' should be a list"

            print(f"\n📊 Summary:")
            print(f"   Total messages: {len(data['msgs'])}")

            # Print details of each message
            for i, msg in enumerate(data['msgs'], 1):
                print(f"\n   Message {i}:")
                print(f"      - Role: {msg.get('role', 'N/A')}")
                print(f"      - Content: {msg.get('msg', 'N/A')[:100]}...")
                print(f"      - Timestamp: {msg.get('timestamp', 'N/A')}")
                if 'image_urls' in msg:
                    print(f"      - Images: {len(msg['image_urls'])} image(s)")
                if 'file_attachments' in msg:
                    print(f"      - Files: {len(msg['file_attachments'])} file(s)")

            return True
        else:
            print(f"\n❌ FAILED: Expected 200, got {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        print(f"\n🔍 Full traceback:")
        traceback.print_exc()
        return False


def test_retrieve_messages_no_session():
    """
    Test retrieving messages without session ID
    """
    print("\n" + "="*80)
    print("TEST: Retrieve Messages - No Session ID")
    print("="*80)

    headers = {
        'Authorization': f'Bearer {TEST_TOKEN}',
        'Content-Type': 'application/json'
    }

    try:
        response = requests.get(ENDPOINT, headers=headers)

        print(f"\n📥 Response:")
        print(f"   Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Returns empty messages: {data}")
            return True
        else:
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False


def test_retrieve_messages_invalid_session():
    """
    Test retrieving messages with invalid session ID
    """
    print("\n" + "="*80)
    print("TEST: Retrieve Messages - Invalid Session ID")
    print("="*80)

    headers = {
        'Authorization': f'Bearer {TEST_TOKEN}',
        'Content-Type': 'application/json'
    }

    params = {
        'msgId': 'invalid-session-id-12345'
    }

    try:
        response = requests.get(ENDPOINT, headers=headers, params=params)

        print(f"\n📥 Response:")
        print(f"   Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Returns empty messages: {data}")
            return True
        else:
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False


def check_database_directly():
    """
    Check if messages exist in the database using AWS CLI (if available)
    """
    print("\n" + "="*80)
    print("DEBUG: Check Database Directly")
    print("="*80)

    try:
        import boto3
        from botocore.exceptions import ClientError

        print("\n🔍 Attempting to query DynamoDB directly...")

        # Try to check if ChatMessages table has data
        dynamodb = boto3.client('dynamodb')

        for session_id in SESSION_IDS:
            user_id = "34d8b4a8-4021-7045-6939-08c7f7000abb"  # From JWT token
            pk = f"USER#{user_id}#SESSION#{session_id}"

            print(f"\n   Querying: {pk}")

            try:
                response = dynamodb.query(
                    TableName='ChatMessages',
                    KeyConditionExpression='PK = :pk',
                    ExpressionAttributeValues={
                        ':pk': {'S': pk}
                    },
                    Limit=5
                )

                count = response.get('Count', 0)
                print(f"   ✅ Found {count} messages in ChatMessages table")

                if count == 0:
                    print(f"   ⚠️  No messages found - this might be the issue!")

            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    print(f"   ⚠️  ChatMessages table not found!")
                else:
                    print(f"   ❌ Error: {e}")

    except ImportError:
        print("\n⚠️  boto3 not available for direct DB check")
    except Exception as e:
        print(f"\n⚠️  Could not check database directly: {str(e)}")


def run_all_tests():
    """
    Run all test cases
    """
    print("\n" + "="*80)
    print("RETRIEVE MESSAGES ENDPOINT TEST SUITE")
    print("="*80)
    print(f"Testing endpoint: {ENDPOINT}")
    print(f"Using token: {TEST_TOKEN[:30]}..." if len(TEST_TOKEN) > 30 else f"Using token: {TEST_TOKEN}")

    if TEST_TOKEN == 'your-test-token-here':
        print("\n❌ ERROR: You need to set a valid authentication token!")
        return

    results = {}

    # Test each session
    for session_id in SESSION_IDS:
        results[f'Session {session_id}'] = test_retrieve_messages(session_id)

    # Test edge cases
    results['No Session ID'] = test_retrieve_messages_no_session()
    results['Invalid Session ID'] = test_retrieve_messages_invalid_session()

    # Check database
    check_database_directly()

    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*80)


if __name__ == "__main__":
    run_all_tests()
