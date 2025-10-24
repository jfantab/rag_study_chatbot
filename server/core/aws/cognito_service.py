"""
Cognito user management service for signup and account deletion
"""
import boto3
from botocore.exceptions import ClientError
from constants import AWS_REGION, COGNITO_CLIENT_ID, COGNITO_USER_POOL_ID


def signup_user(email: str, username: str, password: str) -> dict:
    """
    Sign up a new user using AWS Cognito

    Args:
        email: User's email address
        username: Desired username
        password: User's password

    Returns:
        dict: Success response with user_sub and confirmation details

    Raises:
        ClientError: If Cognito operation fails
    """
    cognito_client = boto3.client('cognito-idp', region_name=AWS_REGION)

    try:
        response = cognito_client.sign_up(
            ClientId=COGNITO_CLIENT_ID,
            Username=username,
            Password=password,
            UserAttributes=[
                {
                    'Name': 'email',
                    'Value': email
                }
            ]
        )

        return {
            "success": True,
            "message": "User signed up successfully. Please check your email for verification.",
            "user_sub": response.get('UserSub'),
            "confirmation_required": response.get('CodeDeliveryDetails') is not None
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']

        # Map Cognito errors to user-friendly messages
        error_mapping = {
            'UsernameExistsException': "Username already exists",
            'InvalidPasswordException': "Password does not meet requirements",
            'InvalidParameterException': "Invalid email or username format"
        }

        user_message = error_mapping.get(error_code, f"Signup failed: {error_message}")
        print(f"Cognito signup error: {error_code} - {error_message}")

        raise Exception(user_message)


def delete_user_account(username: str) -> dict:
    """
    Delete a user account from AWS Cognito

    Args:
        username: Username to delete

    Returns:
        dict: Success response

    Raises:
        ClientError: If Cognito operation fails
    """
    cognito_client = boto3.client('cognito-idp', region_name=AWS_REGION)

    try:
        cognito_client.admin_delete_user(
            UserPoolId=COGNITO_USER_POOL_ID,
            Username=username
        )

        print(f"Successfully deleted user: {username}")

        return {
            "success": True,
            "message": "Account deleted successfully"
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']

        # Map Cognito errors to user-friendly messages
        error_mapping = {
            'UserNotFoundException': "User not found",
            'NotAuthorizedException': "Not authorized to delete this account"
        }

        user_message = error_mapping.get(error_code, f"Account deletion failed: {error_message}")
        print(f"Cognito delete user error: {error_code} - {error_message}")

        raise Exception(user_message)
