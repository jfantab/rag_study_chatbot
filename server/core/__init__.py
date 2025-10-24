"""
Core module for RAG Chatbot server

Organized into:
- aws/: AWS service integrations (Bedrock, Cognito, DynamoDB, S3)
- services/: Business logic services (Auth, Chat, PDF)
- utils/: Utility functions (Message processing, PDF utilities)
"""

# Re-export commonly used items for backward compatibility
from .aws import (
    bedrock_service,
    cognito_service,
    dynamodb_service,
    s3_utils
)

from .services import (
    auth_service,
    chat_service,
    model_service,
    pdf_service
)

from .utils import (
    message_utils,
    pdf_utils
)

__all__ = [
    'aws',
    'services',
    'utils',
]
