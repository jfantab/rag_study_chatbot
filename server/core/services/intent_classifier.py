"""
Intent classification service for routing user queries
Classifies user input into KB_QUESTION, GENERAL_CHAT, or GREETING
"""
import os
import json
import boto3
from constants import AWS_REGION

# Initialize Bedrock runtime client
bedrock_runtime_client = boto3.client('bedrock-runtime', region_name=AWS_REGION)

# Use Claude Haiku for fast, cheap intent classification
INTENT_CLASSIFIER_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"

# Configuration
ENABLE_INTENT_CLASSIFICATION = os.getenv('ENABLE_INTENT_CLASSIFICATION', 'true').lower() == 'true'


def classify_intent(user_input: str) -> str:
    """
    Classify user intent using a lightweight LLM call

    Args:
        user_input: The user's message/query

    Returns:
        One of: 'KB_QUESTION', 'GENERAL_CHAT', 'GREETING'
    """
    # Skip classification if disabled
    if not ENABLE_INTENT_CLASSIFICATION:
        print("⚙️ Intent classification disabled, defaulting to KB_QUESTION")
        return 'KB_QUESTION'

    # Skip classification for very short inputs (likely greetings)
    if len(user_input.strip()) < 3:
        print("🎯 Very short input detected, classifying as GREETING")
        return 'GREETING'

    classification_prompt = f"""You are an intent classifier for a RAG chatbot system. Your job is to classify user queries into one of three categories:

1. KB_QUESTION - Questions that require searching through uploaded documents/knowledge base
   Examples: "What does the contract say about payment terms?", "Summarize the project proposal", "Find information about pricing in the document"

2. GENERAL_CHAT - General questions or conversations that don't require document search
   Examples: "What's the weather like?", "Tell me a joke", "How do I cook pasta?", "Explain quantum physics"

3. GREETING - Simple greetings and pleasantries
   Examples: "Hi", "Hello", "Hey there", "Good morning", "How are you?"

User query: "{user_input}"

Respond with ONLY one word: KB_QUESTION, GENERAL_CHAT, or GREETING. No explanation, no punctuation."""

    try:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 20,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "user",
                    "content": classification_prompt
                }
            ]
        }

        response = bedrock_runtime_client.invoke_model(
            modelId=INTENT_CLASSIFIER_MODEL,
            body=json.dumps(body)
        )

        response_body = json.loads(response['body'].read())

        # Extract the classification
        if 'content' in response_body and len(response_body['content']) > 0:
            intent = response_body['content'][0]['text'].strip().upper()

            # Validate the intent
            if intent in ['KB_QUESTION', 'GENERAL_CHAT', 'GREETING']:
                print(f"🎯 Intent classified: {intent} for query: '{user_input[:50]}...'")
                return intent
            else:
                # Fallback to KB_QUESTION if invalid response
                print(f"⚠️ Invalid intent response: {intent}, defaulting to KB_QUESTION")
                return 'KB_QUESTION'

        # Default fallback
        print("⚠️ No valid response from classifier, defaulting to KB_QUESTION")
        return 'KB_QUESTION'

    except Exception as e:
        print(f"❌ Intent classification error: {str(e)}, defaulting to KB_QUESTION")
        return 'KB_QUESTION'


def should_use_knowledge_base(user_input: str) -> bool:
    """
    Convenience function to determine if knowledge base should be queried

    Args:
        user_input: The user's message/query

    Returns:
        True if KB should be queried, False otherwise
    """
    intent = classify_intent(user_input)
    return intent == 'KB_QUESTION'