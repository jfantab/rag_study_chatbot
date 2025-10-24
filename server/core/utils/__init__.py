"""
Utility functions for message processing and PDF operations
"""

from .message_utils import (
    validate_chat_request,
    upload_base64_images_to_s3,
    process_image_attachments,
    is_pdf_file,
    separate_pdf_files,
    normalize_response_format,
    extract_file_metadata
)

# PDF utilities
from . import pdf_utils

__all__ = [
    # Message utilities
    'validate_chat_request',
    'upload_base64_images_to_s3',
    'process_image_attachments',
    'is_pdf_file',
    'separate_pdf_files',
    'normalize_response_format',
    'extract_file_metadata',
]
