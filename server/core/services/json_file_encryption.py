#!/usr/bin/env python3
"""
JSON File Encryption Service
Handles encrypted file storage in JSON format with encrypted filenames and file bodies
"""

import os
import json
import uuid
import base64
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union

from .file_encryption import FileEncryptionService, MetadataEncryption
from core.services.encryption import AESMessageEncryption


class JsonFileEncryptionService:
    """
    Service for encrypting and storing files in JSON format with encrypted filenames and content
    """

    # JSON format version for future compatibility
    CURRENT_FORMAT_VERSION = "2.0"
    ENCRYPTION_ALGORITHM = "fernet-aes256"

    def __init__(self, user_key: str = None, user_id: str = None):
        """
        Initialize JSON file encryption service

        Args:
            user_key: Encryption key (from environment if not provided)
            user_id: User's identity ID for metadata encryption
        """
        # Use existing file encryption service as base
        self.base_service = FileEncryptionService(user_key=user_key, user_id=user_id)
        self.user_id = user_id

        # Quick access to encryption components
        self.file_encryption = self.base_service.base_encryption
        self.metadata_encryption = self.base_service.metadata_encryption

    def create_encrypted_json_file(
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
        Create encrypted JSON structure for file storage

        Args:
            file_data: Raw file bytes
            filename: Original filename (will be encrypted)
            file_tags: Optional list of tags
            file_description: Optional file description
            file_category: Optional file category
            custom_fields: Optional custom metadata
            knowledge_base_metadata: Optional KB metadata

        Returns:
            Dictionary representing encrypted JSON file structure
        """
        try:
            # Generate unique file ID
            file_id = str(uuid.uuid4())

            # Calculate integrity hash of original file
            integrity_hash = hashlib.sha256(file_data).hexdigest()

            # Encrypt file content using existing AES encryption
            encrypted_file_body = self.file_encryption.encrypt_file_data(file_data)

            # Encrypt filename using metadata encryption
            encrypted_filename = None
            if self.metadata_encryption:
                encrypted_filename = self.metadata_encryption.encrypt_metadata_field(filename)
            else:
                # Fallback: store filename in plaintext if encryption not available
                print("⚠️  Warning: Metadata encryption not available, storing filename in plaintext")

            # Build JSON structure
            json_structure = {
                "format_version": self.CURRENT_FORMAT_VERSION,
                "encryption_algorithm": self.ENCRYPTION_ALGORITHM,
                "file_id": file_id,
                "encrypted_filename": encrypted_filename,
                "encrypted_file_body": encrypted_file_body,
                "metadata": {
                    "original_size": len(file_data),
                    "mime_type": self.base_service.get_mime_type(filename),
                    "upload_date": datetime.utcnow().isoformat(),
                    "integrity_hash": integrity_hash,
                    "uploaded_by_user": self.user_id
                },
                "encrypted_metadata": {}
            }

            # Add encrypted metadata fields if encryption available
            if self.metadata_encryption:
                try:
                    if file_tags:
                        json_structure["encrypted_metadata"]["tags"] = \
                            self.metadata_encryption.encrypt_metadata_field(file_tags)

                    if file_description:
                        json_structure["encrypted_metadata"]["description"] = \
                            self.metadata_encryption.encrypt_metadata_field(file_description)

                    if file_category:
                        json_structure["encrypted_metadata"]["category"] = \
                            self.metadata_encryption.encrypt_metadata_field(file_category)

                    if custom_fields:
                        json_structure["encrypted_metadata"]["custom_fields"] = \
                            self.metadata_encryption.encrypt_metadata_field(custom_fields)

                    if knowledge_base_metadata:
                        json_structure["encrypted_metadata"]["kb_metadata"] = \
                            self.metadata_encryption.encrypt_metadata_field(knowledge_base_metadata)

                except Exception as e:
                    print(f"⚠️  Warning: Failed to encrypt some metadata fields: {str(e)}")
            else:
                # Store unencrypted fallback metadata
                if file_tags:
                    json_structure["metadata"]["fallback_tags"] = file_tags
                if file_description:
                    json_structure["metadata"]["fallback_description"] = file_description
                if file_category:
                    json_structure["metadata"]["fallback_category"] = file_category

            # Add fallback filename if encryption failed
            if not encrypted_filename:
                json_structure["metadata"]["fallback_filename"] = filename

            return json_structure

        except Exception as e:
            print(f"❌ Error creating encrypted JSON file: {str(e)}")
            raise

    def parse_encrypted_json_file(self, json_data: Union[str, Dict]) -> Tuple[bytes, Dict[str, Any]]:
        """
        Parse and decrypt JSON file structure

        Args:
            json_data: JSON string or dictionary

        Returns:
            Tuple of (decrypted_file_bytes, file_metadata_dict)
        """
        try:
            # Parse JSON if string
            if isinstance(json_data, str):
                parsed_data = json.loads(json_data)
            else:
                parsed_data = json_data

            # Validate format version
            format_version = parsed_data.get("format_version", "1.0")
            if format_version != self.CURRENT_FORMAT_VERSION:
                print(f"⚠️  Warning: JSON format version {format_version} may not be fully compatible")

            # Decrypt file content
            encrypted_file_body = parsed_data.get("encrypted_file_body")
            if not encrypted_file_body:
                raise ValueError("Missing encrypted_file_body in JSON structure")

            decrypted_file_data = self.file_encryption.decrypt_file_data(encrypted_file_body)

            # Verify file integrity
            original_hash = parsed_data.get("metadata", {}).get("integrity_hash")
            if original_hash:
                calculated_hash = hashlib.sha256(decrypted_file_data).hexdigest()
                if calculated_hash != original_hash:
                    print(f"⚠️  File integrity check failed: {calculated_hash} != {original_hash}")

            # Extract basic metadata
            metadata = parsed_data.get("metadata", {})
            file_info = {
                "file_id": parsed_data.get("file_id"),
                "format_version": format_version,
                "encryption_algorithm": parsed_data.get("encryption_algorithm"),
                "file_size": metadata.get("original_size", len(decrypted_file_data)),
                "mime_type": metadata.get("mime_type"),
                "upload_date": metadata.get("upload_date"),
                "integrity_hash": original_hash,
                "uploaded_by_user": metadata.get("uploaded_by_user"),
                "is_encrypted": True,
                "storage_format": "json"
            }

            # Decrypt filename
            encrypted_filename = parsed_data.get("encrypted_filename")
            if encrypted_filename and self.metadata_encryption:
                try:
                    file_info["filename"] = self.metadata_encryption.decrypt_metadata_field(encrypted_filename)
                    file_info["filename_encrypted"] = True
                except Exception as e:
                    print(f"⚠️  Failed to decrypt filename: {str(e)}")
                    file_info["filename"] = f"[ENCRYPTED_FILENAME_{file_info.get('file_id', 'unknown')}]"
                    file_info["filename_decryption_error"] = True
            elif metadata.get("fallback_filename"):
                # Use fallback filename
                file_info["filename"] = metadata["fallback_filename"]
                file_info["filename_encrypted"] = False
            else:
                file_info["filename"] = f"[UNKNOWN_FILE_{file_info.get('file_id', 'unknown')}]"
                file_info["filename_encrypted"] = False

            # Decrypt additional metadata
            encrypted_metadata = parsed_data.get("encrypted_metadata", {})
            if encrypted_metadata and self.metadata_encryption:
                try:
                    if "tags" in encrypted_metadata:
                        file_info["tags"] = self.metadata_encryption.decrypt_metadata_field(
                            encrypted_metadata["tags"]
                        )

                    if "description" in encrypted_metadata:
                        file_info["description"] = self.metadata_encryption.decrypt_metadata_field(
                            encrypted_metadata["description"]
                        )

                    if "category" in encrypted_metadata:
                        file_info["category"] = self.metadata_encryption.decrypt_metadata_field(
                            encrypted_metadata["category"]
                        )

                    if "custom_fields" in encrypted_metadata:
                        file_info["custom_fields"] = self.metadata_encryption.decrypt_metadata_field(
                            encrypted_metadata["custom_fields"]
                        )

                    if "kb_metadata" in encrypted_metadata:
                        file_info["kb_metadata"] = self.metadata_encryption.decrypt_metadata_field(
                            encrypted_metadata["kb_metadata"]
                        )

                except Exception as e:
                    print(f"⚠️  Failed to decrypt some metadata fields: {str(e)}")
                    file_info["metadata_decryption_error"] = True

            # Add fallback metadata if available
            for fallback_key in ["fallback_tags", "fallback_description", "fallback_category"]:
                if fallback_key in metadata:
                    actual_key = fallback_key.replace("fallback_", "")
                    if actual_key not in file_info:
                        file_info[actual_key] = metadata[fallback_key]

            return decrypted_file_data, file_info

        except Exception as e:
            print(f"❌ Error parsing encrypted JSON file: {str(e)}")
            raise

    def detect_storage_format(self, file_content: Union[str, bytes], s3_metadata: Dict[str, str] = None) -> str:
        """
        Detect if file is stored in JSON or binary format

        Args:
            file_content: File content from S3
            s3_metadata: S3 metadata dictionary

        Returns:
            "json" or "binary"
        """
        try:
            # Check S3 metadata first
            if s3_metadata:
                storage_format = s3_metadata.get("storage-format", "")
                if "json" in storage_format.lower():
                    return "json"
                elif s3_metadata.get("content-encrypted") == "true":
                    return "binary"  # Legacy binary format

            # Try to parse as JSON
            if isinstance(file_content, bytes):
                try:
                    file_content = file_content.decode('utf-8')
                except UnicodeDecodeError:
                    return "binary"

            if isinstance(file_content, str):
                try:
                    parsed = json.loads(file_content)
                    # Check for JSON format indicators
                    if (isinstance(parsed, dict) and
                        "format_version" in parsed and
                        "encrypted_file_body" in parsed):
                        return "json"
                except json.JSONDecodeError:
                    pass

            # Default to binary format
            return "binary"

        except Exception as e:
            print(f"⚠️  Error detecting storage format: {str(e)}")
            return "binary"  # Safe fallback

    def generate_json_s3_key(self, user_id: str, original_filename: str = None) -> str:
        """
        Generate S3 key for JSON encrypted file

        Args:
            user_id: User's identity ID
            original_filename: Optional original filename for extension preservation

        Returns:
            S3 key for JSON encrypted file
        """
        file_id = str(uuid.uuid4())

        # Preserve file extension for easier identification
        extension = ""
        if original_filename and '.' in original_filename:
            extension = f".{original_filename.split('.')[-1]}"

        return f"users/{user_id}/encrypted_{file_id}{extension}.json"

    def validate_json_structure(self, json_data: Dict[str, Any]) -> bool:
        """
        Validate JSON file structure

        Args:
            json_data: Parsed JSON dictionary

        Returns:
            True if valid, False otherwise
        """
        try:
            required_fields = [
                "format_version",
                "file_id",
                "encrypted_file_body",
                "metadata"
            ]

            for field in required_fields:
                if field not in json_data:
                    print(f"❌ Missing required field: {field}")
                    return False

            # Validate metadata structure
            metadata = json_data["metadata"]
            required_metadata = ["original_size", "upload_date"]

            for field in required_metadata:
                if field not in metadata:
                    print(f"❌ Missing required metadata field: {field}")
                    return False

            return True

        except Exception as e:
            print(f"❌ Error validating JSON structure: {str(e)}")
            return False


def create_json_file_encryption_service(user_key: str = None, user_id: str = None) -> JsonFileEncryptionService:
    """
    Convenience function to create JsonFileEncryptionService instance

    Args:
        user_key: Encryption key (from environment if not provided)
        user_id: User's identity ID

    Returns:
        JsonFileEncryptionService instance
    """
    return JsonFileEncryptionService(user_key=user_key, user_id=user_id)