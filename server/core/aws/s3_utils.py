"""
S3 utility functions for image and file handling
"""
import boto3
import base64
import re
import os
import uuid
from datetime import datetime


def upload_image_to_s3(base64_image: str, user_id: str, chat_id: str, validate_user_fn=None) -> str:
    """
    Upload a base64 image to S3 and return the URL

    Args:
        base64_image: Base64 encoded image data
        user_id: User ID for path organization
        chat_id: Chat ID for path organization
        validate_user_fn: Optional validation function to check user access

    Returns:
        S3 URL of the uploaded image
    """
    # Validate user access if validation function provided
    if validate_user_fn and not validate_user_fn(user_id):
        raise Exception(f"User {user_id} is not authorized to upload files")

    try:
        # Create S3 client
        s3_client = boto3.client('s3')
        bucket_name = "ragchatbotimages"
        S3_BASE_URL = os.getenv('S3_BASE_URL', 's3.amazonaws.com')

        # Generate unique filename
        image_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_key = f"{user_id}/{chat_id}/{timestamp}_{image_id}.jpg"

        # Decode base64 image
        try:
            # Remove data URL prefix if present
            if base64_image.startswith('data:image'):
                base64_image = base64_image.split(',', 1)[1]

            image_data = base64.b64decode(base64_image)
        except Exception as e:
            print(f"Error decoding base64 image: {str(e)}")
            raise

        # Upload to S3 with public read access
        s3_client.put_object(
            Bucket=bucket_name,
            Key=file_key,
            Body=image_data,
            ContentType='image/jpeg',
            CacheControl='max-age=31536000',  # 1 year cache
            ACL='public-read'  # Make image publicly accessible
        )

        # Generate S3 URL
        s3_url = f"https://{bucket_name}.{S3_BASE_URL}/{file_key}"

        print(f"✅ Uploaded image to S3: {s3_url}")
        return s3_url

    except Exception as e:
        print(f"❌ Error uploading image to S3: {str(e)}")
        raise


def upload_image_file_to_s3(file, user_id: str, chat_id: str, validate_user_fn=None) -> dict:
    """
    Upload an image file directly to S3 from a file stream

    Args:
        file: Flask file object from request.files
        user_id: User ID for path organization
        chat_id: Chat ID for path organization
        validate_user_fn: Optional validation function to check user access

    Returns:
        Dictionary with s3_url and s3_key
    """
    # Validate user access if validation function provided
    if validate_user_fn and not validate_user_fn(user_id):
        raise Exception(f"User not authorized to upload files")

    try:
        # Create S3 client
        s3_client = boto3.client('s3')
        bucket_name = "ragchatbotimages"
        S3_BASE_URL = os.getenv('S3_BASE_URL', 's3.amazonaws.com')

        # Generate unique filename
        image_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Get file extension from original filename
        file_ext = 'jpg'
        if '.' in file.filename:
            file_ext = file.filename.rsplit('.', 1)[1].lower()

        file_key = f"{user_id}/{chat_id}/{timestamp}_{image_id}.{file_ext}"

        # Determine content type
        content_type = file.content_type or 'image/jpeg'

        # Upload directly to S3 from file stream (no ACL parameter)
        print(f"📤 Uploading image to S3: {file_key}")
        s3_client.upload_fileobj(
            file.stream,
            bucket_name,
            file_key,
            ExtraArgs={
                'ContentType': content_type,
                'CacheControl': 'max-age=31536000',  # 1 year cache
            }
        )

        # Generate S3 URL
        s3_url = f"https://{bucket_name}.{S3_BASE_URL}/{file_key}"

        print(f"✅ Successfully uploaded image: {s3_url}")

        return {
            "s3_url": s3_url,
            "s3_key": file_key
        }

    except Exception as e:
        print(f"❌ Error uploading image file to S3: {str(e)}")
        raise


def cleanup_user_images(user_id: str) -> dict:
    """
    Delete all S3 images for a user with pagination support

    Args:
        user_id: User ID whose images to delete

    Returns:
        Dictionary with success status and deleted count
    """
    try:
        print(f"Cleaning up all S3 images for user: {user_id}")

        s3_client = boto3.client('s3')
        bucket_name = "ragchatbotimages"
        prefix = f"{user_id}/"

        total_deleted = 0
        continuation_token = None

        # Handle pagination for large numbers of objects
        while True:
            # List objects with pagination
            list_params = {
                'Bucket': bucket_name,
                'Prefix': prefix,
                'MaxKeys': 1000  # AWS maximum per request
            }

            if continuation_token:
                list_params['ContinuationToken'] = continuation_token

            response = s3_client.list_objects_v2(**list_params)

            # Check if any objects were found
            if 'Contents' not in response or len(response['Contents']) == 0:
                break

            # Prepare objects for batch deletion (max 1000 per request)
            objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]

            if objects_to_delete:
                # Delete batch
                delete_response = s3_client.delete_objects(
                    Bucket=bucket_name,
                    Delete={'Objects': objects_to_delete}
                )

                batch_deleted = len(delete_response.get('Deleted', []))
                total_deleted += batch_deleted

                # Check for errors
                if 'Errors' in delete_response:
                    for error in delete_response['Errors']:
                        print(f"Error deleting {error['Key']}: {error['Message']}")

            # Check if there are more objects to process
            if not response.get('IsTruncated', False):
                break

            continuation_token = response.get('NextContinuationToken')

        if total_deleted > 0:
            print(f"Deleted {total_deleted} images for user {user_id}")
            return {
                "success": True,
                "message": f"Successfully deleted {total_deleted} images",
                "deleted_count": total_deleted
            }
        else:
            print(f"No images found for user {user_id}")
            return {"success": True, "message": "No images found", "deleted_count": 0}

    except Exception as e:
        print(f"Error cleaning up user images: {str(e)}")
        raise


def download_s3_image_to_base64(s3_url: str) -> str:
    """Download an image from S3 URL and convert to base64"""
    try:
        # Extract bucket and key from S3 URL
        match = re.match(r'https://([^.]+)\.s3\.amazonaws\.com/(.+)', s3_url)

        if not match:
            raise ValueError(f"Invalid S3 URL format: {s3_url}")

        bucket_name = match.group(1)
        file_key = match.group(2)

        # Download from S3
        s3_client = boto3.client('s3')
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        image_data = response['Body'].read()

        # Convert to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        return base64_image

    except Exception as e:
        print(f"❌ Error downloading S3 image: {str(e)}")
        raise
