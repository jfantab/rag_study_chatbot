#!/usr/bin/env python3
"""
File Encryption Service for S3 Storage
Extends existing AES encryption with file-specific features and S3 metadata support
"""

import os
import json
import hashlib
import base64
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Import existing encryption class
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.services.encryption import AESMessageEncryption


class MetadataEncryption:
    """Handles encryption of sensitive metadata fields"""

    def __init__(self, user_key: str, user_id: str):
        """
        Initialize metadata encryption with user-specific key derivation

        Args:
            user_key: User's encryption key
            user_id: User's identity ID for salt generation
        """
        self.user_id = user_id
        self.user_key = user_key.encode() if isinstance(user_key, str) else user_key

        # Generate user-specific salt for metadata encryption
        salt = hashlib.sha256(f"metadata_salt_{user_id}".encode()).digest()

        # Derive metadata-specific key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        fernet_key = base64.urlsafe_b64encode(kdf.derive(self.user_key))
        self.cipher_suite = Fernet(fernet_key)

    def encrypt_metadata_field(self, value: Any) -> str:
        """
        Encrypt a metadata field value

        Args:
            value: Value to encrypt (string, dict, list, etc.)

        Returns:
            Base64 encoded encrypted string
        """
        try:
            if value is None:
                return ""

            # Convert complex objects to JSON
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True)
            elif isinstance(value, bytes):
                # If already bytes, decode to string first
                value = value.decode('utf-8')
            elif not isinstance(value, str):
                value = str(value)

            if not value:
                return ""

            encrypted_data = self.cipher_suite.encrypt(value.encode('utf-8'))
            return base64.b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            print(f"❌ Error encrypting metadata field: {str(e)}")
            raise

    def decrypt_metadata_field(self, encrypted_value: str) -> Any:
        """
        Decrypt a metadata field value

        Args:
            encrypted_value: Base64 encoded encrypted string

        Returns:
            Decrypted value (attempts JSON parsing)
        """
        try:
            if not encrypted_value:
                return None

            # Handle both string and bytes input
            if isinstance(encrypted_value, bytes):
                encrypted_data = base64.b64decode(encrypted_value)
            else:
                encrypted_data = base64.b64decode(encrypted_value.encode('utf-8'))
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            decrypted_str = decrypted_data.decode('utf-8')

            # Try to parse as JSON
            try:
                return json.loads(decrypted_str)
            except json.JSONDecodeError:
                return decrypted_str

        except Exception as e:
            print(f"❌ Error decrypting metadata field: {str(e)}")
            return None


class FileEncryptionService:
    """
    Enhanced file encryption service with S3 metadata support
    """

    def __init__(self, user_key: str = None, user_id: str = None):
        """
        Initialize file encryption service

        Args:
            user_key: Encryption key (from environment if not provided)
            user_id: User's identity ID for metadata encryption
        """
        # Get key from environment if not provided
        if user_key is None:
            user_key = os.getenv('CHAT_ENCRYPTION_KEY', 'default_key')

        # Initialize base encryption
        self.base_encryption = AESMessageEncryption(user_key)

        # Initialize metadata encryption if user_id provided
        self.metadata_encryption = None
        if user_id and user_key:
            self.metadata_encryption = MetadataEncryption(user_key, user_id)

        self.user_id = user_id

    def generate_file_id(self) -> str:
        """Generate unique file ID"""
        return str(uuid.uuid4())

    def calculate_file_hash(self, file_data: bytes) -> str:
        """
        Calculate SHA-256 hash of file data for integrity verification

        Args:
            file_data: Raw file bytes

        Returns:
            Hex string of SHA-256 hash
        """
        return hashlib.sha256(file_data).hexdigest()

    def get_mime_type(self, filename: str) -> str:
        """
        Determine MIME type from filename

        Args:
            filename: Name of the file

        Returns:
            MIME type string
        """
        extension = filename.lower().split('.')[-1] if '.' in filename else ''

        mime_types = {
            'pdf': 'application/pdf',
            'txt': 'text/plain',
            'json': 'application/json',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        }

        return mime_types.get(extension, 'application/octet-stream')

    def validate_metadata_size(self, metadata_dict: Dict[str, str]) -> Dict[str, str]:
        """
        Validate S3 metadata size (2KB limit) and handle overflow

        Args:
            metadata_dict: Dictionary of metadata key-value pairs

        Returns:
            Validated metadata dictionary (may be truncated)
        """
        # Calculate total metadata size
        total_size = sum(len(k) + len(v) for k, v in metadata_dict.items())

        if total_size <= 1800:  # Leave buffer under 2KB limit
            return metadata_dict

        # Handle overflow by removing non-essential encrypted fields
        essential_fields = [
            'original-filename', 'file-size', 'mime-type', 'upload-date',
            'file-id', 'content-encrypted', 'encryption-algorithm',
            'metadata-version', 'integrity-hash'
        ]

        # Keep essential fields, truncate others
        truncated_metadata = {k: v for k, v in metadata_dict.items()
                            if k in essential_fields}

        print(f"⚠️  Metadata truncated due to size limit: {total_size} bytes")
        return truncated_metadata

    def create_s3_metadata(
        self,
        filename: str,
        file_size: int,
        file_hash: str,
        file_tags: List[str] = None,
        file_description: str = None,
        file_category: str = None,
        custom_fields: Dict[str, Any] = None,
        knowledge_base_metadata: Dict[str, Any] = None
    ) -> Dict[str, str]:
        """
        Create S3 metadata with encrypted filename and sensitive fields

        Args:
            filename: Original filename (will be encrypted)
            file_size: Size of original file in bytes
            file_hash: SHA-256 hash of original file
            file_tags: Optional list of tags
            file_description: Optional file description
            file_category: Optional file category
            custom_fields: Optional custom metadata fields
            knowledge_base_metadata: Optional Knowledge Base specific metadata

        Returns:
            Dictionary of S3 metadata (keys must be lowercase with hyphens)
        """
        file_id = self.generate_file_id()

        # Start with plaintext operational metadata (no filename)
        metadata = {
            # PLAINTEXT - Operational data (minimal for privacy)
            'file-size': str(file_size),
            'mime-type': self.get_mime_type(filename),
            'upload-date': datetime.utcnow().isoformat(),
            'file-id': file_id,
            'integrity-hash': file_hash,

            # SYSTEM - Encryption info
            'content-encrypted': 'true',
            'encryption-algorithm': 'AES-256-Fernet',
            'metadata-version': 'v2.0',  # Updated version for encrypted filenames
        }

        # Add user ID if available
        if self.user_id:
            metadata['uploaded-by-user'] = self.user_id

        # Add encrypted sensitive metadata (including filename)
        if self.metadata_encryption:
            try:
                # ENCRYPT THE FILENAME - this is the key change
                metadata['encrypted-filename'] = self.metadata_encryption.encrypt_metadata_field(filename)

                if file_tags:
                    metadata['encrypted-tags'] = self.metadata_encryption.encrypt_metadata_field(file_tags)

                if file_description:
                    metadata['encrypted-description'] = self.metadata_encryption.encrypt_metadata_field(file_description)

                if file_category:
                    metadata['encrypted-category'] = self.metadata_encryption.encrypt_metadata_field(file_category)

                if custom_fields:
                    metadata['encrypted-custom-fields'] = self.metadata_encryption.encrypt_metadata_field(custom_fields)

                if knowledge_base_metadata:
                    metadata['encrypted-kb-metadata'] = self.metadata_encryption.encrypt_metadata_field(knowledge_base_metadata)

            except Exception as e:
                print(f"⚠️  Failed to encrypt some metadata fields: {str(e)}")
                # Fallback: store filename in plaintext if encryption fails
                metadata['original-filename'] = filename
        else:
            # Fallback: store filename in plaintext if no metadata encryption
            metadata['original-filename'] = filename

        # Validate metadata size
        return self.validate_metadata_size(metadata)

    def encrypt_file_with_metadata(
        self,
        file_data: bytes,
        filename: str,
        file_tags: List[str] = None,
        file_description: str = None,
        file_category: str = None,
        custom_fields: Dict[str, Any] = None,
        knowledge_base_metadata: Dict[str, Any] = None
    ) -> Tuple[str, Dict[str, str]]:
        """
        Encrypt file and create metadata for S3 storage

        Args:
            file_data: Raw file bytes
            filename: Original filename
            file_tags: Optional list of tags
            file_description: Optional file description
            file_category: Optional file category
            custom_fields: Optional custom metadata
            knowledge_base_metadata: Optional KB metadata

        Returns:
            Tuple of (encrypted_file_base64, s3_metadata_dict)
        """
        try:
            # Calculate hash of original file
            file_hash = self.calculate_file_hash(file_data)

            # Encrypt file content
            encrypted_data = self.base_encryption.encrypt_file_data(file_data)

            # Create S3 metadata
            s3_metadata = self.create_s3_metadata(
                filename=filename,
                file_size=len(file_data),
                file_hash=file_hash,
                file_tags=file_tags,
                file_description=file_description,
                file_category=file_category,
                custom_fields=custom_fields,
                knowledge_base_metadata=knowledge_base_metadata
            )

            return encrypted_data, s3_metadata

        except Exception as e:
            print(f"❌ Error encrypting file with metadata: {str(e)}")
            raise

    def decrypt_file_with_metadata(
        self,
        encrypted_file_data: str,
        s3_metadata: Dict[str, str]
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Decrypt file and metadata from S3

        Args:
            encrypted_file_data: Base64 encoded encrypted file
            s3_metadata: S3 metadata dictionary

        Returns:
            Tuple of (decrypted_file_bytes, decrypted_metadata_dict)
        """
        try:
            # Decrypt file content
            decrypted_data = self.base_encryption.decrypt_file_data(encrypted_file_data)

            # Verify file integrity
            calculated_hash = self.calculate_file_hash(decrypted_data)
            stored_hash = s3_metadata.get('integrity-hash', '')

            if stored_hash and calculated_hash != stored_hash:
                print(f"⚠️  File integrity check failed: {calculated_hash} != {stored_hash}")

            # Extract plaintext metadata
            file_info = {
                'file_size': int(s3_metadata.get('file-size', 0)),
                'mime_type': s3_metadata.get('mime-type'),
                'upload_date': s3_metadata.get('upload-date'),
                'file_id': s3_metadata.get('file-id'),
                'integrity_hash': s3_metadata.get('integrity-hash'),
                'is_encrypted': s3_metadata.get('content-encrypted') == 'true',
                'encryption_algorithm': s3_metadata.get('encryption-algorithm'),
                'metadata_version': s3_metadata.get('metadata-version', 'v1.0'),
            }

            # Handle filename - support both old (plaintext) and new (encrypted) formats
            if 'encrypted-filename' in s3_metadata and self.metadata_encryption:
                # New format: filename is encrypted
                try:
                    file_info['filename'] = self.metadata_encryption.decrypt_metadata_field(
                        s3_metadata['encrypted-filename']
                    )
                    file_info['filename_encrypted'] = True
                except Exception as e:
                    print(f"⚠️  Failed to decrypt filename: {str(e)}")
                    file_info['filename'] = f"[ENCRYPTED_FILENAME_{s3_metadata.get('file-id', 'unknown')}]"
                    file_info['filename_decryption_error'] = True
            elif 'original-filename' in s3_metadata:
                # Old format: filename is plaintext
                file_info['filename'] = s3_metadata.get('original-filename')
                file_info['filename_encrypted'] = False
            else:
                # Fallback: no filename available
                file_info['filename'] = f"[UNKNOWN_FILE_{s3_metadata.get('file-id', 'unknown')}]"
                file_info['filename_encrypted'] = False

            # Decrypt sensitive metadata if available
            if self.metadata_encryption:
                try:
                    if 'encrypted-tags' in s3_metadata:
                        file_info['tags'] = self.metadata_encryption.decrypt_metadata_field(
                            s3_metadata['encrypted-tags']
                        )

                    if 'encrypted-description' in s3_metadata:
                        file_info['description'] = self.metadata_encryption.decrypt_metadata_field(
                            s3_metadata['encrypted-description']
                        )

                    if 'encrypted-category' in s3_metadata:
                        file_info['category'] = self.metadata_encryption.decrypt_metadata_field(
                            s3_metadata['encrypted-category']
                        )

                    if 'encrypted-custom-fields' in s3_metadata:
                        file_info['custom_fields'] = self.metadata_encryption.decrypt_metadata_field(
                            s3_metadata['encrypted-custom-fields']
                        )

                    if 'encrypted-kb-metadata' in s3_metadata:
                        file_info['knowledge_base_metadata'] = self.metadata_encryption.decrypt_metadata_field(
                            s3_metadata['encrypted-kb-metadata']
                        )

                except Exception as e:
                    print(f"⚠️  Failed to decrypt some metadata fields: {str(e)}")
                    file_info['metadata_decryption_error'] = True
            else:
                # Indicate that encrypted metadata exists but can't be decrypted
                encrypted_fields = [k for k in s3_metadata.keys() if k.startswith('encrypted-')]
                if encrypted_fields:
                    file_info['has_encrypted_metadata'] = True
                    file_info['encrypted_fields'] = encrypted_fields

            return decrypted_data, file_info

        except Exception as e:
            print(f"❌ Error decrypting file with metadata: {str(e)}")
            raise

    def is_file_encrypted(self, s3_metadata: Dict[str, str]) -> bool:
        """
        Check if file is encrypted based on S3 metadata

        Args:
            s3_metadata: S3 metadata dictionary

        Returns:
            True if file is encrypted, False otherwise
        """
        return s3_metadata.get('content-encrypted') == 'true'

    def generate_encrypted_s3_key(self, user_id: str, original_filename: str = None) -> str:
        """
        Generate S3 key for encrypted file

        Args:
            user_id: User's identity ID
            original_filename: Optional original filename for reference

        Returns:
            S3 key for encrypted file
        """
        file_id = self.generate_file_id()

        # Include file extension if available for easier identification
        extension = ""
        if original_filename and '.' in original_filename:
            extension = f".{original_filename.split('.')[-1]}"

        return f"users/{user_id}/encrypted_{file_id}{extension}.enc"


# Convenience function for backward compatibility
def create_file_encryption_service(user_key: str = None, user_id: str = None) -> FileEncryptionService:
    """
    Create a FileEncryptionService instance

    Args:
        user_key: Encryption key (from environment if not provided)
        user_id: User's identity ID

    Returns:
        FileEncryptionService instance
    """
    return FileEncryptionService(user_key=user_key, user_id=user_id)