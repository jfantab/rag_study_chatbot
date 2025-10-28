"""
Bedrock wrapper service for query routing and image processing
"""
import os
import json
import requests
from core.aws.bedrock_service import retrieve_and_generate_bedrock
from core.aws.s3_utils import download_s3_image_to_base64


def query_bedrock(question, sesh_id, user_id=None, images=None, files=None, current_model_id=None, bedrock_api_url=None):
    """
    Query Bedrock - with toggle between direct access and Lambda
    Set environment variable USE_DIRECT_BEDROCK=false to use Lambda (old method)

    Args:
        question: User question/input
        sesh_id: Session ID
        user_id: User ID for filtering
        images: List of image URLs or base64 strings
        files: List of file attachments
        current_model_id: Model ID to use
        bedrock_api_url: Lambda API URL (for legacy mode)

    Returns:
        Response text from Bedrock
    """
    use_direct_bedrock = os.getenv('USE_DIRECT_BEDROCK', 'true').lower() == 'true'

    if use_direct_bedrock:
        # NEW: Direct Bedrock access (bypasses Lambda - faster!)
        print("🚀 Using direct Bedrock access (bypassing Lambda)")

        # Convert S3 URLs to base64 for images
        base64_images = None
        if images and len(images) > 0:
            base64_images = []
            for i, img in enumerate(images):
                try:
                    # Check if it's an S3 URL or already base64
                    if img.startswith('http'):
                        print(f"🔄 Converting S3 URL to base64: image {i+1}/{len(images)}")
                        base64_img, media_type = download_s3_image_to_base64(img)
                        print(f"✅ Converted image {i+1} to base64 (media_type: {media_type})")
                        base64_images.append(base64_img)
                    else:
                        # Already base64, use as-is (legacy support)
                        base64_images.append(img)
                except Exception as e:
                    print(f"❌ Failed to process image {i+1}: {str(e)}")
                    import traceback
                    print(f"❌ Traceback: {traceback.format_exc()}")

        # Call direct Bedrock function
        answer = retrieve_and_generate_bedrock(
            user_input=question,
            session_id=sesh_id,
            model_id=current_model_id,
            user_id=user_id,
            images=base64_images,
            files=files
        )
        return answer

    else:
        # OLD: Lambda method (kept as fallback)
        print("⚠️ Using Lambda method (slower, but kept for compatibility)")
        url = bedrock_api_url

        payload_data = {
            "question": question,
            "sessionId": sesh_id,
            "model_id": current_model_id,
            "filters": {
                "equals": {
                "key": "user_id",
                "value": user_id
                }
            }
        }

        # Add images if provided - convert S3 URLs to base64 for Bedrock
        if images and len(images) > 0:
            base64_images = []
            for i, img in enumerate(images):
                try:
                    # Check if it's an S3 URL or already base64
                    if img.startswith('http'):
                        print(f"🔄 Converting S3 URL to base64: image {i+1}/{len(images)}")
                        base64_img, media_type = download_s3_image_to_base64(img)
                        base64_images.append(base64_img)
                    else:
                        # Already base64, use as-is (legacy support)
                        base64_images.append(img)
                except Exception as e:
                    print(f"❌ Failed to process image {i+1}: {str(e)}")

            if base64_images:
                payload_data["images"] = base64_images
                print(f"🖼️ Including {len(base64_images)} images in the request")

        # Add files if provided
        if files and len(files) > 0:
            payload_data["files"] = files
            print(f"📄 Including {len(files)} files in the request")

        payload = json.dumps(payload_data)

        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.request("POST", url, headers=headers, data=payload)

        return response.text
