"""
Image management routes for S3 image operations
"""
import uuid
import boto3
from datetime import datetime
from flask import Blueprint, jsonify, request
from core.services.auth_service import require_auth
from core.aws.s3_utils import cleanup_user_images
from constants import S3_BASE_URL
from core.aws.dynamodb_service import validate_user_access

# Create Blueprint
image_bp = Blueprint('image', __name__)


@image_bp.route("/upload-image", methods=["POST"])
@require_auth
def upload_image_endpoint(authenticated_user_id):
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


@image_bp.route("/cleanup_user_images", methods=["POST"])
@require_auth
def cleanup_user_images_route(authenticated_user_id):
    """Delete all S3 images for the authenticated user"""
    try:
        result = cleanup_user_images(authenticated_user_id)
        return jsonify(result), 200
    except Exception as e:
        print(f"Error in cleanup_user_images route: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500