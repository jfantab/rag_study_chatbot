"""
AWS integration services for Bedrock, Cognito, DynamoDB, and S3
"""

from .bedrock_service import (
    should_fallback_to_llm,
    invoke_direct_llm_bedrock,
    invoke_direct_llm_bedrock_stream,
    retrieve_and_generate_bedrock,
    retrieve_and_generate_bedrock_stream,
    bedrock_agent_runtime_client,
    bedrock_runtime_client,
)

from .document_processing import (
    extract_pdf_text_with_textract,
    extract_text_from_document,
    textract_client
)

# Bedrock wrapper exports
from . import bedrock_wrapper

# Cognito service exports
from . import cognito_service

from .dynamodb_service import (
    get_chat_pk,
    get_chat_sk,
    get_history_pk,
    get_current_timestamp,
    generate_user_pk,
    generate_history_sk,
    validate_user_access,
    save_chat_message_to_dynamodb,
    ensure_chat_sessions_table_exists
)

from .s3_utils import (
    download_s3_image_to_base64,
    upload_image_to_s3
)

__all__ = [
    # Bedrock
    'extract_pdf_text_with_textract',
    'extract_text_from_document',
    'should_fallback_to_llm',
    'invoke_direct_llm_bedrock',
    'invoke_direct_llm_bedrock_stream',
    'retrieve_and_generate_bedrock',
    'retrieve_and_generate_bedrock_stream',
    'bedrock_agent_runtime_client',
    'bedrock_runtime_client',
    'textract_client',
    # DynamoDB
    'get_chat_pk',
    'get_chat_sk',
    'get_history_pk',
    'get_current_timestamp',
    'generate_user_pk',
    'generate_history_sk',
    'validate_user_access',
    'save_chat_message_to_dynamodb',
    'ensure_chat_sessions_table_exists',
    # S3
    'download_s3_image_to_base64',
    'upload_image_to_s3',
]
