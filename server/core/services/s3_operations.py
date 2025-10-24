#!/usr/bin/env python3
"""
S3 Operations with File Encryption Support
Handles encrypted file storage and retrieval with metadata
Supports both binary and JSON storage formats
"""

import os
import boto3
import json
import base64
from typing import Dict, List, Any, Optional, Tuple
from botocore.exceptions import ClientError

from .file_encryption import FileEncryptionService
from .json_file_encryption import JsonFileEncryptionService
from constants import AWS_REGION


class EncryptedS3Service:
    """
    S3 service with integrated file encryption and metadata handling
    """

    def __init__(self, bucket_name: str, user_id: str, user_key: str):
        """
        Initialize encrypted S3 service

        Args:
            bucket_name: S3 bucket name
            user_id: User's identity ID
            user_key: User's encryption key
        """
        self.bucket_name = bucket_name
        self.user_id = user_id
        self.s3_client = boto3.client('s3', region_name=AWS_REGION)

        # Initialize both encryption services
        self.encryption_service = FileEncryptionService(user_key=user_key, user_id=user_id)
        self.json_encryption_service = JsonFileEncryptionService(user_key=user_key, user_id=user_id)

        # Check feature flag for JSON format
        self.use_json_format = os.getenv('USE_JSON_FILE_FORMAT', 'false').lower() == 'true'

    def upload_encrypted_file(
        self,
        file_data: bytes,
        filename: str,
        file_tags: List[str] = None,
        file_description: str = None,
        file_category: str = None,
        custom_fields: Dict[str, Any] = None,
        knowledge_base_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Upload an encrypted file to S3 with metadata

        Args:
            file_data: Raw file bytes
            filename: Original filename
            file_tags: Optional list of tags
            file_description: Optional file description
            file_category: Optional file category
            custom_fields: Optional custom metadata
            knowledge_base_metadata: Optional KB metadata

        Returns:
            Dictionary with upload results
        """
        try:
            if self.use_json_format:
                return self._upload_json_format(
                    file_data, filename, file_tags, file_description,
                    file_category, custom_fields, knowledge_base_metadata
                )
            else:
                return self._upload_binary_format(
                    file_data, filename, file_tags, file_description,
                    file_category, custom_fields, knowledge_base_metadata
                )

        except Exception as e:
            print(f"❌ Error uploading encrypted file: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _upload_json_format(
        self,
        file_data: bytes,
        filename: str,
        file_tags: List[str] = None,
        file_description: str = None,
        file_category: str = None,
        custom_fields: Dict[str, Any] = None,
        knowledge_base_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Upload file using JSON format"""
        try:
            print(f"📄 Uploading file in JSON format: {filename}")

            # Create encrypted JSON structure
            json_structure = self.json_encryption_service.create_encrypted_json_file(
                file_data=file_data,
                filename=filename,
                file_tags=file_tags,
                file_description=file_description,
                file_category=file_category,
                custom_fields=custom_fields,
                knowledge_base_metadata=knowledge_base_metadata
            )

            # Generate S3 key for JSON file
            s3_key = self.json_encryption_service.generate_json_s3_key(
                user_id=self.user_id,
                original_filename=filename
            )

            # Convert JSON to string and upload
            json_string = json.dumps(json_structure, indent=None)

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json_string.encode('utf-8'),
                ContentType='application/json',
                Metadata={
                    'storage-format': 'encrypted-json-v2',
                    'original-filename': filename,  # Backup reference
                    'user-id': self.user_id
                },
                ServerSideEncryption='AES256'
            )

            return {
                'success': True,
                'storage_format': 'json',
                'file_id': json_structure['file_id'],
                's3_key': s3_key,
                'filename': filename,
                'file_size': len(file_data),
                'json_size': len(json_string),
                'upload_date': json_structure['metadata']['upload_date']
            }

        except Exception as e:
            print(f"❌ Error uploading JSON format file: {str(e)}")
            raise

    def _upload_binary_format(
        self,
        file_data: bytes,
        filename: str,
        file_tags: List[str] = None,
        file_description: str = None,
        file_category: str = None,
        custom_fields: Dict[str, Any] = None,
        knowledge_base_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Upload file using legacy binary format"""
        try:
            print(f"📄 Uploading file in binary format: {filename}")

            # Encrypt file and create metadata (existing method)
            encrypted_data, s3_metadata = self.encryption_service.encrypt_file_with_metadata(
                file_data=file_data,
                filename=filename,
                file_tags=file_tags,
                file_description=file_description,
                file_category=file_category,
                custom_fields=custom_fields,
                knowledge_base_metadata=knowledge_base_metadata
            )

            # Generate S3 key
            s3_key = self.encryption_service.generate_encrypted_s3_key(
                user_id=self.user_id,
                original_filename=filename
            )

            # Upload to S3
            encrypted_bytes = base64.b64decode(encrypted_data)

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=encrypted_bytes,
                Metadata=s3_metadata,
                ServerSideEncryption='AES256'
            )

            return {
                'success': True,
                'storage_format': 'binary',
                'file_id': s3_metadata['file-id'],
                's3_key': s3_key,
                'filename': filename,
                'file_size': len(file_data),
                'encrypted_size': len(encrypted_data),
                'upload_date': s3_metadata['upload-date']
            }

        except Exception as e:
            print(f"❌ Error uploading binary format file: {str(e)}")
            raise

    def download_encrypted_file(self, s3_key: str) -> Dict[str, Any]:
        """
        Download and decrypt a file from S3

        Args:
            s3_key: S3 object key

        Returns:
            Dictionary with file data and metadata
        """
        try:
            # Get object from S3
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            file_content = response['Body'].read()
            s3_metadata = response.get('Metadata', {})

            # Detect storage format
            storage_format = self._detect_file_format(file_content, s3_metadata)

            if storage_format == 'json':
                return self._download_json_format(s3_key, file_content, s3_metadata)
            elif storage_format == 'binary':
                return self._download_binary_format(s3_key, file_content, s3_metadata)
            else:
                # Legacy unencrypted file
                return self._handle_unencrypted_file(s3_key, file_content, s3_metadata)

        except Exception as e:
            print(f"❌ Error downloading encrypted file: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _detect_file_format(self, file_content: bytes, s3_metadata: Dict[str, str]) -> str:
        """Detect if file is JSON or binary format"""
        try:
            # Check S3 metadata first
            storage_format = s3_metadata.get('storage-format', '')
            if 'json' in storage_format.lower():
                return 'json'
            elif s3_metadata.get('content-encrypted') == 'true':
                return 'binary'

            # Try to detect from content
            format_detected = self.json_encryption_service.detect_storage_format(file_content, s3_metadata)
            return format_detected

        except Exception as e:
            print(f"⚠️  Error detecting file format: {str(e)}")
            return 'binary'  # Safe fallback

    def _download_json_format(self, s3_key: str, file_content: bytes, s3_metadata: Dict[str, str]) -> Dict[str, Any]:
        """Download and decrypt JSON format file"""
        try:
            print(f"📄 Downloading JSON format file: {s3_key}")

            # Parse JSON content
            json_string = file_content.decode('utf-8')

            # Decrypt using JSON service
            decrypted_data, file_info = self.json_encryption_service.parse_encrypted_json_file(json_string)

            return {
                'success': True,
                'storage_format': 'json',
                'file_data': decrypted_data,
                'metadata': file_info,
                's3_key': s3_key
            }

        except Exception as e:
            print(f"❌ Error downloading JSON format file: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _download_binary_format(self, s3_key: str, file_content: bytes, s3_metadata: Dict[str, str]) -> Dict[str, Any]:
        """Download and decrypt binary format file"""
        try:
            print(f"📄 Downloading binary format file: {s3_key}")

            # Convert to base64 for existing decryption method
            encrypted_data = base64.b64encode(file_content).decode('utf-8')

            # Check if file is encrypted
            if not self.encryption_service.is_file_encrypted(s3_metadata):
                return self._handle_unencrypted_file(s3_key, file_content, s3_metadata)

            # Decrypt using existing binary service
            decrypted_data, file_info = self.encryption_service.decrypt_file_with_metadata(
                encrypted_file_data=encrypted_data,
                s3_metadata=s3_metadata
            )

            return {
                'success': True,
                'storage_format': 'binary',
                'file_data': decrypted_data,
                'metadata': file_info,
                's3_key': s3_key
            }

        except Exception as e:
            print(f"❌ Error downloading binary format file: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def _handle_unencrypted_file(self, s3_key: str, file_bytes: bytes, s3_metadata: Dict[str, str]) -> Dict[str, Any]:
        """
        Handle legacy unencrypted files

        Args:
            s3_key: S3 object key
            file_bytes: Raw file bytes from S3
            s3_metadata: S3 metadata

        Returns:
            Dictionary with file data and legacy metadata
        """
        try:
            # file_bytes is already the raw file content for legacy files

            # Extract filename from S3 key
            filename = s3_key.split('/')[-1]

            # Create basic metadata for unencrypted file
            file_info = {
                'filename': filename,
                'file_size': len(file_bytes),
                'mime_type': s3_metadata.get('content-type', 'application/octet-stream'),
                'is_encrypted': False,
                'legacy_file': True,
                's3_key': s3_key
            }

            # Add any existing metadata
            file_info.update(s3_metadata)

            return {
                'success': True,
                'file_data': file_bytes,
                'metadata': file_info,
                's3_key': s3_key
            }

        except Exception as e:
            print(f"❌ Error handling unencrypted file: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def list_user_files(self, include_metadata: bool = True) -> List[Dict[str, Any]]:
        """
        List all files for the user with optional metadata decryption

        Args:
            include_metadata: Whether to decrypt and include metadata

        Returns:
            List of file information dictionaries
        """
        try:
            # List objects for user
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"users/{self.user_id}/"
            )

            files = []
            for obj in response.get('Contents', []):
                s3_key = obj['Key']

                try:
                    # Get object metadata
                    head_response = self.s3_client.head_object(
                        Bucket=self.bucket_name,
                        Key=s3_key
                    )
                    s3_metadata = head_response.get('Metadata', {})

                    # Basic file info
                    file_info = {
                        's3_key': s3_key,
                        'last_modified': obj['LastModified'].isoformat(),
                        'size_on_s3': obj['Size']
                    }

                    if self.encryption_service.is_file_encrypted(s3_metadata):
                        # Encrypted file - handle both new encrypted filenames and old plaintext filenames
                        filename = s3_key.split('/')[-1]  # Default fallback

                        # Try encrypted filename first (v2.0+)
                        if 'encrypted-filename' in s3_metadata and self.encryption_service.metadata_encryption:
                            try:
                                filename = self.encryption_service.metadata_encryption.decrypt_metadata_field(
                                    s3_metadata['encrypted-filename']
                                )
                            except Exception as e:
                                print(f"⚠️  Failed to decrypt filename for {s3_key}: {str(e)}")
                                filename = f"[ENCRYPTED_FILENAME_{s3_metadata.get('file-id', 'unknown')}]"
                        # Fallback to legacy plaintext filename
                        elif 'original-filename' in s3_metadata:
                            filename = s3_metadata.get('original-filename')

                        file_info.update({
                            'filename': filename,
                            'file_size': int(s3_metadata.get('file-size', 0)),
                            'mime_type': s3_metadata.get('mime-type'),
                            'upload_date': s3_metadata.get('upload-date'),
                            'file_id': s3_metadata.get('file-id'),
                            'is_encrypted': True,
                            'encryption_algorithm': s3_metadata.get('encryption-algorithm'),
                            'metadata_version': s3_metadata.get('metadata-version', 'v1.0')
                        })

                        # Decrypt metadata if requested
                        if include_metadata and self.encryption_service.metadata_encryption:
                            try:
                                if 'encrypted-tags' in s3_metadata:
                                    file_info['tags'] = self.encryption_service.metadata_encryption.decrypt_metadata_field(
                                        s3_metadata['encrypted-tags']
                                    )

                                if 'encrypted-category' in s3_metadata:
                                    file_info['category'] = self.encryption_service.metadata_encryption.decrypt_metadata_field(
                                        s3_metadata['encrypted-category']
                                    )

                                if 'encrypted-description' in s3_metadata:
                                    file_info['description'] = self.encryption_service.metadata_encryption.decrypt_metadata_field(
                                        s3_metadata['encrypted-description']
                                    )

                            except Exception as e:
                                print(f"⚠️  Failed to decrypt metadata for {s3_key}: {str(e)}")
                                file_info['metadata_decryption_error'] = True
                    else:
                        # Unencrypted legacy file
                        filename = s3_key.split('/')[-1]
                        file_info.update({
                            'filename': filename,
                            'file_size': obj['Size'],
                            'mime_type': s3_metadata.get('content-type', 'application/octet-stream'),
                            'is_encrypted': False,
                            'legacy_file': True
                        })

                    files.append(file_info)

                except Exception as e:
                    print(f"⚠️  Error processing file {s3_key}: {str(e)}")
                    # Add basic info even if metadata processing fails
                    files.append({
                        's3_key': s3_key,
                        'filename': s3_key.split('/')[-1],
                        'size_on_s3': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'processing_error': str(e)
                    })

            return files

        except Exception as e:
            print(f"❌ Error listing user files: {str(e)}")
            return []

    def delete_file(self, s3_key: str) -> Dict[str, Any]:
        """
        Delete a file from S3

        Args:
            s3_key: S3 object key

        Returns:
            Dictionary with deletion results
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return {
                'success': True,
                'deleted_key': s3_key
            }
        except Exception as e:
            print(f"❌ Error deleting file: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_file_metadata_only(self, s3_key: str) -> Dict[str, Any]:
        """
        Get only metadata for a file without downloading content

        Args:
            s3_key: S3 object key

        Returns:
            Dictionary with metadata
        """
        try:
            # Get object metadata only
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            s3_metadata = response.get('Metadata', {})

            if self.encryption_service.is_file_encrypted(s3_metadata):
                # Extract decrypted metadata
                _, file_info = self.encryption_service.decrypt_file_with_metadata("", s3_metadata)
                return {
                    'success': True,
                    'metadata': file_info
                }
            else:
                # Legacy file metadata
                return {
                    'success': True,
                    'metadata': {
                        'filename': s3_key.split('/')[-1],
                        'is_encrypted': False,
                        'legacy_file': True,
                        's3_metadata': s3_metadata
                    }
                }

        except Exception as e:
            print(f"❌ Error getting file metadata: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }


def create_encrypted_s3_service(bucket_name: str, user_id: str, user_key: str) -> EncryptedS3Service:
    """
    Create an EncryptedS3Service instance

    Args:
        bucket_name: S3 bucket name
        user_id: User's identity ID
        user_key: User's encryption key

    Returns:
        EncryptedS3Service instance
    """
    return EncryptedS3Service(bucket_name=bucket_name, user_id=user_id, user_key=user_key)