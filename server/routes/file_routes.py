"""
File management routes for S3 file operations and PDF processing
"""
import os
import json
from flask import Blueprint, jsonify, request

from core.services.auth_service import require_auth
from core.aws.dynamodb_service import validate_user_access
from core.services.s3_operations import create_encrypted_s3_service
from core.services.pdf_processing import PDFProcessor

file_bp = Blueprint('files', __name__)


@file_bp.route("/list_s3_files", methods=["GET"])
@require_auth
def list_s3_files_enhanced(authenticated_user_id):
    """List files with encryption support"""
    if not validate_user_access(authenticated_user_id):
        return jsonify({"error": f"User {authenticated_user_id} is not authorized to list files"}), 403

    try:
        # Get query parameters
        include_metadata = request.args.get('include_metadata', 'true').lower() == 'true'

        # Create encrypted S3 service
        from constants import S3_DOCUMENT_BUCKET
        bucket_name = S3_DOCUMENT_BUCKET
        user_key = os.getenv('CHAT_ENCRYPTION_KEY', 'default_key')
        s3_service = create_encrypted_s3_service(
            bucket_name=bucket_name,
            user_id=authenticated_user_id,
            user_key=user_key
        )

        # List files
        files = s3_service.list_user_files(include_metadata=include_metadata)

        return jsonify({
            "files": files,
            "total_count": len(files),
            "user_id": authenticated_user_id,
            "include_metadata": include_metadata
        }), 200

    except Exception:
        return jsonify({"error": "Failed to list files"}), 500


@file_bp.route("/list_s3_files_encrypted", methods=["GET"])
@require_auth
def list_s3_files_with_server_decryption(authenticated_user_id):
    """List files with server-side decryption of filenames and metadata"""
    if not validate_user_access(authenticated_user_id):
        return jsonify({"error": f"User {authenticated_user_id} is not authorized to list files"}), 403

    try:
        import boto3

        # Import encryption services
        from core.services.file_encryption import FileEncryptionService

        # Create S3 client directly to get raw metadata
        from constants import S3_DOCUMENT_BUCKET
        s3_client = boto3.client('s3')
        bucket_name = S3_DOCUMENT_BUCKET
        user_prefix = f"users/{authenticated_user_id}/"

        # List objects for user
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=user_prefix
        )

        # Initialize encryption service for this user
        encryption_service = FileEncryptionService(user_id=authenticated_user_id)
        metadata_encryption = encryption_service.metadata_encryption

        files = []
        for obj in response.get('Contents', []):
            s3_key = obj['Key']

            # Skip JSON format encrypted files (these are handled separately)
            if s3_key.endswith('.json'):
                continue

            try:
                # Get object metadata (raw, unprocessed)
                head_response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
                s3_metadata = head_response.get('Metadata', {})

                # Basic file info
                file_info = {
                    's3_key': s3_key,
                    'last_modified': obj['LastModified'].isoformat(),
                    'size_on_s3': obj['Size'],
                    'file_size': int(s3_metadata.get('file-size', obj['Size'])),
                    'mime_type': s3_metadata.get('mime-type', 'application/octet-stream'),
                    'upload_date': s3_metadata.get('upload-date'),
                    'file_id': s3_metadata.get('file-id'),
                    'is_encrypted': s3_metadata.get('content-encrypted') == 'true',
                    'metadata_version': s3_metadata.get('metadata-version', 'v1.0'),
                    'encryption_algorithm': s3_metadata.get('encryption-algorithm'),
                    'storage_format': 'binary'
                }

                # Decrypt filename on server side
                if 'encrypted-filename' in s3_metadata:
                    try:
                        decrypted_filename = metadata_encryption.decrypt_metadata_field(s3_metadata['encrypted-filename'])
                        file_info['filename'] = decrypted_filename
                        file_info['filename_encrypted'] = False
                    except Exception:
                        file_info['filename'] = f"[Encrypted File] {s3_key.split('/')[-1]}"
                        file_info['filename_encrypted'] = False
                elif 'original-filename' in s3_metadata:
                    file_info['filename'] = s3_metadata['original-filename']
                    file_info['filename_encrypted'] = False
                else:
                    file_info['filename'] = s3_key.split('/')[-1]
                    file_info['filename_encrypted'] = False

                # Decrypt other metadata fields on server side
                decrypted_metadata = {}
                for key, value in s3_metadata.items():
                    if key.startswith('encrypted-') and key != 'encrypted-filename':
                        try:
                            decrypted_value = metadata_encryption.decrypt_metadata_field(value)
                            clean_key = key.replace('encrypted-', '')
                            decrypted_metadata[clean_key] = decrypted_value
                        except Exception:
                            decrypted_metadata[key] = f"[Decrypt Error] {value[:20]}..."

                file_info['metadata'] = decrypted_metadata
                files.append(file_info)

            except Exception as e:
                files.append({
                    's3_key': s3_key,
                    'filename': s3_key.split('/')[-1],
                    'size_on_s3': obj['Size'],
                    'file_size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'processing_error': str(e),
                    'is_encrypted': False,
                    'filename_encrypted': False,
                    'storage_format': 'binary'
                })

        # Also check for JSON format encrypted files
        json_files = []
        try:
            from core.services.json_file_encryption import JsonFileEncryptionService

            json_encryption_service = JsonFileEncryptionService(user_id=authenticated_user_id)

            # List JSON files
            json_response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=user_prefix,
                Delimiter='/'
            )

            for obj in json_response.get('Contents', []):
                if obj['Key'].endswith('.json') and not obj['Key'].endswith('.metadata.json'):
                    try:
                        # Download and parse JSON file
                        json_obj = s3_client.get_object(Bucket=bucket_name, Key=obj['Key'])
                        json_content = json.loads(json_obj['Body'].read().decode('utf-8'))

                        if 'encrypted_filename' in json_content and 'encrypted_file_body' in json_content:
                            # This is a JSON format encrypted file
                            decrypted_filename = json_encryption_service.metadata_encryption.decrypt_metadata_field(json_content['encrypted_filename'])

                            json_file_info = {
                                's3_key': obj['Key'],
                                'filename': decrypted_filename,
                                'file_size': json_content.get('original_file_size', obj['Size']),
                                'size_on_s3': obj['Size'],
                                'mime_type': json_content.get('mime_type', 'application/octet-stream'),
                                'last_modified': obj['LastModified'].isoformat(),
                                'upload_date': json_content.get('upload_date'),
                                'is_encrypted': True,
                                'filename_encrypted': False,
                                'storage_format': 'json',
                                'metadata_version': json_content.get('metadata_version', 'v1.0')
                            }

                            json_files.append(json_file_info)

                    except Exception:
                        pass  # Skip files that can't be processed

        except Exception:
            pass  # JSON encryption service not available

        # Combine both file types
        all_files = files + json_files

        return jsonify({
            "files": all_files,
            "total_count": len(all_files),
            "user_id": authenticated_user_id,
            "client_decryption_required": False,
            "metadata_version": "v2.0",
            "server_decryption": True
        }), 200

    except Exception:
        return jsonify({"error": "Failed to list files"}), 500


@file_bp.route("/upload_to_s3", methods=["POST"])
@require_auth
def upload_to_s3(authenticated_user_id):
    """Upload a file to S3 with encryption"""
    if not validate_user_access(authenticated_user_id):
        return jsonify({"error": f"User {authenticated_user_id} is not authorized to upload files"}), 403

    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        if file:
            # Read file data
            file_data = file.read()

            # Get optional metadata from form data
            file_tags = request.form.get('tags', '').split(',') if request.form.get('tags') else None
            file_description = request.form.get('description', None)
            file_category = request.form.get('category', None)

            # Parse custom fields if provided
            custom_fields = None
            if request.form.get('custom_fields'):
                try:
                    custom_fields = json.loads(request.form.get('custom_fields'))
                except json.JSONDecodeError:
                    pass  # Ignore invalid JSON

            try:
                # Create encrypted S3 service
                from constants import S3_DOCUMENT_BUCKET
                bucket_name = S3_DOCUMENT_BUCKET
                user_key = os.getenv('CHAT_ENCRYPTION_KEY', 'default_key')
                s3_service = create_encrypted_s3_service(
                    bucket_name=bucket_name,
                    user_id=authenticated_user_id,
                    user_key=user_key
                )

                # Upload encrypted file
                result = s3_service.upload_encrypted_file(
                    file_data=file_data,
                    filename=file.filename,
                    file_tags=file_tags,
                    file_description=file_description,
                    file_category=file_category,
                    custom_fields=custom_fields
                )

                if result['success']:
                    response_data = {
                        "message": "File uploaded and encrypted successfully",
                        "filename": file.filename,
                        "file_id": result['file_id'],
                        "s3_key": result['s3_key'],
                        "original_size": result['file_size'],
                        "upload_date": result['upload_date'],
                        "is_encrypted": True,
                        "storage_format": result.get('storage_format', 'binary')
                    }

                    # Add format-specific size information
                    if result.get('storage_format') == 'json':
                        response_data["json_size"] = result.get('json_size')
                    else:
                        response_data["encrypted_size"] = result.get('encrypted_size')

                    return jsonify(response_data), 200
                else:
                    return jsonify({"error": f"Failed to upload encrypted file: {result['error']}"}), 500

            except Exception:
                return jsonify({"error": "Failed to upload encrypted file to S3"}), 500

    except Exception:
        return jsonify({"error": "Failed to upload file"}), 500


@file_bp.route("/pdf_processing_status", methods=["GET"])
@require_auth
def get_pdf_processing_status(authenticated_user_id):
    """Get the processing status of PDF documents"""
    try:
        pdf_hash = request.args.get('pdf_hash')
        if not pdf_hash:
            return jsonify({"error": "pdf_hash parameter is required"}), 400

        pdf_processor = PDFProcessor()
        status_info = pdf_processor.check_kb_document_exists(pdf_hash)

        return jsonify({
            "pdf_hash": pdf_hash,
            "exists": status_info.get('exists', False),
            "status": status_info.get('status', 'unknown'),
            "upload_timestamp": status_info.get('upload_timestamp'),
            "kb_document_id": status_info.get('kb_document_id'),
            "file_metadata": status_info.get('file_metadata', {})
        }), 200

    except Exception:
        return jsonify({"error": "Failed to get processing status"}), 500


@file_bp.route("/download_from_s3", methods=["GET"])
@require_auth
def download_from_s3(authenticated_user_id):
    """Download and decrypt a file from S3 with enhanced debugging"""
    import boto3
    from flask import Response

    if not validate_user_access(authenticated_user_id):
        return jsonify({"error": f"User {authenticated_user_id} is not authorized to download files"}), 403

    try:
        s3_key = request.args.get('s3_key')

        if not s3_key:
            return jsonify({"error": "s3_key parameter is required"}), 400

        # Validate that the file belongs to the user
        if not s3_key.startswith(f"users/{authenticated_user_id}/"):
            return jsonify({"error": "Access denied to this file"}), 403

        # Import encryption services
        from core.services.file_encryption import FileEncryptionService
        from core.services.json_file_encryption import JsonFileEncryptionService

        # Create S3 client
        from constants import S3_DOCUMENT_BUCKET
        s3_client = boto3.client('s3')
        bucket_name = S3_DOCUMENT_BUCKET

        try:
            # Check if this is a JSON format file or binary format
            if s3_key.endswith('.json'):
                # Download JSON file
                response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                json_content = json.loads(response['Body'].read().decode('utf-8'))

                # Initialize JSON encryption service
                json_service = JsonFileEncryptionService(user_id=authenticated_user_id)

                # Parse and decrypt JSON file
                file_data, file_metadata = json_service.parse_encrypted_json_file(json_content)

                # Return decrypted file
                response = Response(
                    file_data,
                    mimetype=file_metadata.get('mime_type', 'application/octet-stream'),
                    headers={
                        'Content-Disposition': f'attachment; filename="{file_metadata.get("filename", "download")}"',
                        'Content-Type': file_metadata.get('mime_type', 'application/octet-stream'),
                        'X-File-ID': file_metadata.get('file_id', ''),
                        'X-Is-Encrypted': 'True',
                        'X-Original-Size': str(file_metadata.get('file_size', len(file_data))),
                        'X-Storage-Format': 'json'
                    }
                )
                return response

            else:
                # Get object and its metadata
                response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                file_data = response['Body'].read()
                s3_metadata = response.get('Metadata', {})

                # Check if file is encrypted
                if s3_metadata.get('content-encrypted') == 'true':
                    # Initialize encryption service
                    encryption_service = FileEncryptionService(user_id=authenticated_user_id)

                    # Decrypt file data
                    decrypted_data = encryption_service.base_encryption.decrypt_file_data(file_data)
                    file_data = decrypted_data

                # Determine filename
                filename = s3_metadata.get('original-filename', s3_key.split('/')[-1])

                # Decrypt filename if it's encrypted
                if 'encrypted-filename' in s3_metadata:
                    try:
                        metadata_encryption = encryption_service.metadata_encryption
                        if metadata_encryption:
                            filename = metadata_encryption.decrypt_metadata_field(s3_metadata['encrypted-filename'])
                    except Exception:
                        pass  # Use original filename if decryption fails

                # Return decrypted file
                response = Response(
                    file_data,
                    mimetype=s3_metadata.get('mime-type', 'application/octet-stream'),
                    headers={
                        'Content-Disposition': f'attachment; filename="{filename}"',
                        'Content-Type': s3_metadata.get('mime-type', 'application/octet-stream'),
                        'X-File-ID': s3_metadata.get('file-id', ''),
                        'X-Is-Encrypted': s3_metadata.get('content-encrypted', 'false'),
                        'X-Original-Size': str(s3_metadata.get('file-size', len(file_data))),
                        'X-Storage-Format': 'binary'
                    }
                )
                return response

        except Exception as e:
            return jsonify({"error": f"Failed to process file: {str(e)}"}), 500

    except Exception:
        return jsonify({"error": "Failed to download file"}), 500
