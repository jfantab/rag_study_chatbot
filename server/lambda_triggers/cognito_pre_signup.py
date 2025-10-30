"""
AWS Lambda function for Cognito Pre-Signup trigger
Automatically confirms users and verifies their email on signup
"""

import json


def lambda_handler(event, context):
    """
    Pre-signup Lambda trigger for AWS Cognito

    This function is invoked by Cognito during user signup to:
    - Auto-confirm the user (no email verification needed)
    - Auto-verify the user's email attribute

    Args:
        event (dict): Cognito Pre-Signup trigger event
        context (object): Lambda context object

    Returns:
        dict: Modified event with response parameters
    """

    # Log the event for debugging (helpful for troubleshooting)
    print(f"Pre-signup trigger invoked")
    print(f"Event: {json.dumps(event, indent=2)}")

    # Extract user attributes
    user_attributes = event.get('request', {}).get('userAttributes', {})
    email = user_attributes.get('email', 'unknown')
    username = event.get('userName', 'unknown')

    # Auto-confirm the user (skips email verification step)
    event['response']['autoConfirmUser'] = True

    # Auto-verify the user's email attribute
    event['response']['autoVerifyEmail'] = True

    # Optional: Auto-verify phone number if you're collecting it
    # event['response']['autoVerifyPhone'] = True

    print(f"✅ Auto-confirming user: {username} ({email})")

    # Return the modified event
    return event
