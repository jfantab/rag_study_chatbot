"""
Configuration constants for the chatbot server
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Server configuration
PORT = 8000

# AWS Cognito configuration
COGNITO_USER_POOL_ID = os.getenv('COGNITO_USER_POOL_ID')
COGNITO_CLIENT_ID = os.getenv('COGNITO_CLIENT_ID')
COGNITO_IDENTITY_POOL_ID = os.getenv('COGNITO_IDENTITY_POOL_ID', 'us-east-1:9d22c5b6-23df-4aa0-8605-79bce429f576')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# S3 configuration
S3_BASE_URL = "s3.amazonaws.com"
ALLOWED_USER_EMAIL = "johnlu1161@gmail.com"

# S3 Bucket Names
S3_IMAGE_BUCKET = os.getenv('S3_IMAGE_BUCKET', 'ragchatbotimages')
S3_DOCUMENT_BUCKET = os.getenv('S3_DOCUMENT_BUCKET', 'rag-doc-store')

# API Gateway URLs
BEDROCK_API_URL = "https://rf79sz38z3.execute-api.us-east-1.amazonaws.com/dev/chat"
RAG_DOC_STORE_API_URL = "https://6vm4t63uje.execute-api.us-east-1.amazonaws.com/dev/rag-doc-store"

# Intent Classification Configuration
ENABLE_INTENT_CLASSIFICATION = os.getenv('ENABLE_INTENT_CLASSIFICATION', 'true').lower() == 'true'
INTENT_CLASSIFIER_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"

# JWT Authentication Configuration
KEYS_CACHE_DURATION = 3600  # 1 hour

# Available AI models (ON-DEMAND THROUGHPUT ONLY)
# Note: Models requiring Provisioned Throughput have been excluded
MODELS = {
    # === ANTHROPIC CLAUDE MODELS ===
    # Claude 3.5 Family
    "Claude 3.5 Sonnet": "anthropic.claude-3-5-sonnet-20240620-v1:0",

    # Claude 3 Family
    "Claude 3 Sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
    "Claude 3 Haiku": "anthropic.claude-3-haiku-20240307-v1:0",

    # === META LLAMA MODELS ===
    # Llama 3 Family (Base models with on-demand support)
    "Llama 3 70B": "meta.llama3-70b-instruct-v1:0",
    "Llama 3 8B": "meta.llama3-8b-instruct-v1:0",

    # === MISTRAL AI MODELS ===
    "Mistral Large (24.02)": "mistral.mistral-large-2402-v1:0",
    "Mistral Small (24.02)": "mistral.mistral-small-2402-v1:0",
    "Mixtral 8x7B": "mistral.mixtral-8x7b-instruct-v0:1",
    "Mistral 7B": "mistral.mistral-7b-instruct-v0:2",
}

# Default model
DEFAULT_MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"

# Validate required environment variables
def validate_environment():
    """Validate that all required environment variables are set"""
    if not COGNITO_USER_POOL_ID:
        raise ValueError("COGNITO_USER_POOL_ID environment variable is required")
    if not COGNITO_CLIENT_ID:
        raise ValueError("COGNITO_CLIENT_ID environment variable is required")