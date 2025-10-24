"""
Message processing utilities for chat operations
Handles validation, image processing, file processing, and response normalization
"""
import json
from flask import jsonify
from core.aws.s3_utils import upload_image_to_s3


def validate_chat_request(data):
    """
    Validate incoming chat request data

    Args:
        data: Request data dictionary

    Returns:
        tuple: (is_valid, error_response, validated_data)
    """
    print("Chat request received:", data)

    if 'msg' not in data:
        print("ERROR: Missing 'msg' field")
        return False, (jsonify({"error": "Message is not found in request object."}), 400), None

    if 'msg_id' not in data:
        print("ERROR: Missing required msg_id")
        return False, (jsonify({"error": "msg_id is not found in request object."}), 400), None

    question = data["msg"]
    msg_id = data["msg_id"]

    # Accept either base64 images (legacy) or image_urls (new method)
    images = data.get("images", [])  # Legacy base64 images
    image_urls = data.get("image_urls", [])  # New: pre-uploaded S3 URLs
    files = data.get("files", [])

    print(f"Extracted values: msg_id='{msg_id}' (len={len(msg_id) if msg_id else 0})")

    # Log what we received
    attachments = []
    if images:
        attachments.append(f"{len(images)} base64 images")
    if image_urls:
        attachments.append(f"{len(image_urls)} image URLs")
    if files:
        attachments.append(f"{len(files)} files")

    if attachments:
        print(f"Received {', '.join(attachments)}")
    else:
        print("Text-only message")

    if not msg_id or msg_id.strip() == "":
        print("ERROR: Empty msg_id detected")
        return False, (jsonify({"error": "msg_id cannot be empty."}), 400), None

    validated_data = {
        'question': question,
        'msg_id': msg_id,
        'images': images,
        'image_urls': image_urls,
        'files': files
    }

    return True, None, validated_data


def upload_base64_images_to_s3(images, user_id, msg_id):
    """
    Upload base64 encoded images to S3

    Args:
        images: List of base64 encoded images
        user_id: User ID for S3 path
        msg_id: Message ID for S3 path

    Returns:
        list: S3 URLs of uploaded images
    """
    uploaded_urls = []
    print(f"Uploading {len(images)} base64 images to S3 (legacy method)...")

    for i, base64_image in enumerate(images):
        try:
            s3_url = upload_image_to_s3(base64_image, user_id, msg_id)
            uploaded_urls.append(s3_url)
            print(f"Uploaded image {i+1}/{len(images)}: {s3_url}")
        except Exception as e:
            print(f"Failed to upload image {i+1}/{len(images)}: {str(e)}")
            # Continue with other images even if one fails

    return uploaded_urls


def process_image_attachments(images, image_urls, user_id, msg_id):
    """
    Process image attachments - handle both legacy base64 and pre-uploaded URLs

    Args:
        images: List of base64 encoded images (legacy)
        image_urls: List of pre-uploaded S3 URLs
        user_id: User ID for S3 path
        msg_id: Message ID for S3 path

    Returns:
        list: Processed image URLs
    """
    processed_urls = list(image_urls)  # Copy existing URLs

    # Handle legacy base64 images if provided (fallback)
    if images and len(images) > 0:
        uploaded_urls = upload_base64_images_to_s3(images, user_id, msg_id)
        processed_urls.extend(uploaded_urls)
    # If image_urls were provided directly, just log them
    elif image_urls:
        print(f"Using pre-uploaded images: {len(image_urls)} URLs")

    return processed_urls


def is_pdf_file(file_data):
    """
    Check if a file is a PDF based on type or filename

    Args:
        file_data: File data dictionary with 'type' and 'name' fields

    Returns:
        bool: True if file is a PDF
    """
    file_type = file_data.get('type', '').lower()
    file_name = file_data.get('name', '').lower()
    return file_type == 'application/pdf' or file_name.endswith('.pdf')


def separate_pdf_files(files):
    """
    Separate PDF files from other file types

    Args:
        files: List of file data dictionaries

    Returns:
        tuple: (pdf_files, other_files)
    """
    if not files:
        return [], []

    pdf_files = [f for f in files if is_pdf_file(f)]
    other_files = [f for f in files if not is_pdf_file(f)]

    return pdf_files, other_files


def normalize_response_format(answer):
    """
    Normalize response format from different sources (Direct Bedrock vs Lambda)

    Args:
        answer: Response from Bedrock (string or dict)

    Returns:
        str: Normalized answer string
    """
    # Handle response format based on whether we're using direct Bedrock or Lambda
    # Direct Bedrock returns string directly, Lambda returns JSON-wrapped response
    if isinstance(answer, str) and not answer.startswith('{'):
        # Direct Bedrock response - already a string
        return answer
    else:
        # Lambda response - need to parse JSON
        try:
            if isinstance(answer, str):
                answer = json.loads(answer)
            if isinstance(answer, dict) and 'body' in answer:
                return answer['body']['answer']
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error parsing response: {e}, using as-is")

    return answer


def extract_file_metadata(files):
    """
    Extract metadata from file attachments for storage in chat history

    Args:
        files: List of file data dictionaries

    Returns:
        list: List of file metadata dictionaries
    """
    file_metadata = []
    for file_data in files:
        file_info = {
            "name": file_data.get("name", "unknown"),
            "type": file_data.get("type", "unknown"),
            "size": len(file_data.get("content", "")) if file_data.get("content") else 0
        }
        file_metadata.append(file_info)
    return file_metadata
