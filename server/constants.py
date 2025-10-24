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

# Available AI models
MODELS = {
    # Text & Vision Models
    "Claude Sonnet 4": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "Claude 3 Sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
    "Claude Opus 4": "anthropic.claude-opus-4-20250514-v1:0",
    "Llama 3 70B Instruct": "meta.llama3-70b-instruct-v1:0",
    "Llama 3.2 90B Vision Instruct": "meta.llama3-2-90b-instruct-v1:0",
    "Llama 4 Maverick 17B Instruct": "meta.llama3-1-405b-instruct-v1:0",
    "Pegasus 1.2": "twelvelabs.pegasus-1-2-v1:0",
    "Claude Opus 4.1": "anthropic.claude-opus-4-1-20250805-v1:0",

    # Text Only Models
    "Mistral 7B Instruct": "mistral.mistral-7b-instruct-v0:2",
    "DeepSeek-R1": "deepseek.r1-v1:0",
}

# Default model
DEFAULT_MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"

# Validate required environment variables
def validate_environment():
    """Validate that all required environment variables are set"""
    if not COGNITO_USER_POOL_ID:
        raise ValueError("COGNITO_USER_POOL_ID environment variable is required")
    if not COGNITO_CLIENT_ID:
        raise ValueError("COGNITO_CLIENT_ID environment variable is required")