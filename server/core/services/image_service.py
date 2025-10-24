
import os
import uuid
import base64
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from flask import jsonify, request
from jose import jwk, jwt as jose_jwt
from functools import wraps
import time
import requests
from constants import S3_BASE_URL
from core.aws.dynamodb_service import validate_user_access

def upload_image_to_s3(base64_image: str, user_id: str, chat_id: str) -> str:
    """
    Upload a base64 image to S3 and return the URL
    """
    # Validate user access
    if not validate_user_access(user_id):
        raise Exception(f"User {user_id} is not authorized to upload files")

    try:
        # Create S3 client
        s3_client = boto3.client('s3')
        bucket_name = "ragchatbotimages"

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


def download_s3_image_to_base64(s3_url: str) -> str:
    """
    Download an image from S3 URL and convert to base64.
    """
    try:
        # Extract bucket and key from S3 URL
        # Expected format: https://ragchatbotimages.s3.amazonaws.com/user_id/chat_id/filename.jpg
        import re
        match = re.match(r'https://([^.]+)\.s3\.amazonaws\.com/(.+)', s3_url)

        if not match:
            raise ValueError(f"Invalid S3 URL format: {s3_url}")

        bucket_name = match.group(1)
        file_key = match.group(2)

        print(f"📥 Downloading image from S3: {bucket_name}/{file_key}")

        # Download from S3
        s3_client = boto3.client('s3')
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        image_data = response['Body'].read()

        # Convert to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')

        print(f"✅ Downloaded and converted image to base64 ({len(base64_image)} chars)")
        return base64_image

    except Exception as e:
        print(f"❌ Error downloading S3 image: {str(e)}")
        raise

def upload_image_endpoint(app):
    @app.route("/upload-image", methods=["POST"])
    @require_auth
    def upload_image_endpoint_func(authenticated_user_id):
        """
        Upload an image file directly to S3 and return the URL.
        Accepts multipart/form-data with image file.
        """
        try:
            # Check if file is in request
            if 'file' not in request.files:
                return jsonify({"error": "No file provided"}), 400

            file = request.files['file']
            if file.filename == '':
                return jsonify({"error": "Empty filename"}), 400

            # Get user_id from authentication
            user_id = authenticated_user_id

            # Get chat_id from form data or generate new one
            chat_id = request.form.get('chatId', str(uuid.uuid4()))

            # Validate user access
            if not validate_user_access(user_id):
                return jsonify({"error": "User not authorized to upload files"}), 403

            # Create S3 client
            s3_client = boto3.client('s3')
            bucket_name = "ragchatbotimages"

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

            return jsonify({
                "s3_url": s3_url,
                "s3_key": file_key
            }), 200

        except Exception as e:
            print(f"❌ Error in upload-image endpoint: {str(e)}")
            return jsonify({"error": f"Failed to upload image: {str(e)}"}), 500
