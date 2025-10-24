"""
Bedrock service for AWS Bedrock LLM and Knowledge Base interactions
Handles streaming and non-streaming responses
"""
import os
import json
import boto3
from botocore.client import Config
from constants import AWS_REGION
from .document_processing import extract_text_from_document

# Configure retry strategy
retry_config = Config(
    retries={
        'max_attempts': 10,
        'mode': 'adaptive'
    }
)

# Initialize Bedrock clients with retry config
bedrock_agent_runtime_client = boto3.client('bedrock-agent-runtime', region_name=AWS_REGION, config=retry_config)
bedrock_runtime_client = boto3.client('bedrock-runtime', region_name=AWS_REGION, config=retry_config)


# Knowledge Base configuration
KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID", "ADEGC5Q4KM")


def should_fallback_to_llm(kb_response: dict, user_input: str) -> bool:
    """
    Determine if we should fallback to direct LLM based on knowledge base response quality

    Relies on KB system prompt to output "I don't know" when uncertain.
    Includes safety nets for common refusal patterns in case model doesn't follow exactly.
    """
    try:
        if 'output' not in kb_response or 'text' not in kb_response['output']:
            return True

        answer = kb_response['output']['text'].lower().strip()

        # Primary check: Exact match from system prompt
        if answer == "i don't know" or answer == "i don't know.":
            print("⚠️ KB fallback: Exact 'I don't know' response")
            return True

        # Simplified fallback indicators (safety net for model variations)
        fallback_indicators = [
            "i don't know",          # Primary - from system prompt
            "i am unable",           # Catches "Sorry, I am unable to assist..."
            "i'm unable",            # Alternative contraction
            "i cannot find",         # Common variation
            "i don't have",          # Common variation
            "sorry, i",              # Catches polite refusals
        ]

        for indicator in fallback_indicators:
            if indicator in answer:
                print(f"⚠️ KB fallback triggered by: '{indicator}' in response")
                return True

        # Length check: Very short responses are usually unhelpful
        if len(answer) < 15:
            print(f"⚠️ KB fallback: Response too short ({len(answer)} chars)")
            return True

        return False

    except Exception as e:
        print(f"⚠️ Fallback check error: {e}")
        return False  # Don't fallback on error


def invoke_direct_llm_bedrock(user_input: str, model_id: str, session_id: str, user_id: str, images: list = None, files: list = None) -> str:
    """Invoke Bedrock LLM directly without knowledge base"""
    enhanced_input = user_input

    # Process file attachments
    if files and len(files) > 0:
        file_contents = []
        for i, file_data in enumerate(files):
            try:
                file_name = file_data.get('name', f'file_{i+1}')
                file_type = file_data.get('type', 'unknown')
                file_content_b64 = file_data.get('content', '')

                if file_content_b64:
                    extracted_text = extract_text_from_document(file_content_b64, file_name, file_type)
                    file_contents.append(f"\n--- File: {file_name} (Type: {file_type}) ---\n{extracted_text}\n--- End of {file_name} ---\n")
                else:
                    file_contents.append(f"\n--- File: {file_name} (Type: {file_type}) ---\n[File contains no data]\n--- End of {file_name} ---\n")

            except Exception as e:
                file_contents.append(f"\n--- File: {file_name} ---\n[Error processing file: {str(e)}]\n--- End of {file_name} ---\n")

        if file_contents:
            enhanced_input = f"""{user_input}

Attached files ({len(file_contents)} processed):
{''.join(file_contents)}

Please analyze the content from the attached files and provide insights based on the available information."""

    # Build user message content
    user_content = []
    if enhanced_input:
        user_content.append({"type": "text", "text": enhanced_input})

    # Add images if provided
    if images and len(images) > 0:
        for image_base64 in images:
            try:
                if image_base64.startswith('data:image'):
                    image_base64 = image_base64.split(',', 1)[1]

                user_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_base64
                    }
                })
            except Exception as e:
                print(f"❌ Error adding image: {str(e)}")

    # Build request body
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "temperature": 0.1,
        "messages": [
            {
                "role": "user",
                "content": user_content if len(user_content) > 1 else enhanced_input
            }
        ]
    }

    try:
        response = bedrock_runtime_client.invoke_model(
            modelId=model_id,
            body=json.dumps(body)
        )

        response_body = json.loads(response['body'].read())

        if 'content' in response_body:
            content = response_body['content']
            if isinstance(content, list) and len(content) > 0:
                if isinstance(content[0], dict) and 'text' in content[0]:
                    return content[0]['text']
            elif isinstance(content, dict) and 'text' in content:
                return content['text']

        return response_body.get('generation', response_body.get('text', 'Unable to generate response'))

    except Exception as e:
        return f"I apologize, but I'm having trouble processing your request right now. Error: {str(e)}"


def invoke_direct_llm_bedrock_stream(user_input: str, model_id: str, session_id: str, user_id: str, images: list = None, files: list = None):
    """Stream Bedrock LLM response in real-time (yields chunks)"""
    # Same file processing as non-streaming version
    enhanced_input = user_input

    if files and len(files) > 0:
        file_contents = []
        for i, file_data in enumerate(files):
            try:
                file_name = file_data.get('name', f'file_{i+1}')
                file_type = file_data.get('type', 'unknown')
                file_content_b64 = file_data.get('content', '')

                if file_content_b64:
                    extracted_text = extract_text_from_document(file_content_b64, file_name, file_type)
                    file_contents.append(f"\n--- File: {file_name} ---\n{extracted_text}\n")

            except Exception as e:
                file_contents.append(f"\n--- File: {file_name} ---\n[Error: {str(e)}]\n")

        if file_contents:
            enhanced_input = f"{user_input}\n\nAttached files:\n{''.join(file_contents)}"

    user_content = []
    if enhanced_input:
        user_content.append({"type": "text", "text": enhanced_input})

    if images and len(images) > 0:
        for image_base64 in images:
            try:
                if image_base64.startswith('data:image'):
                    image_base64 = image_base64.split(',', 1)[1]
                user_content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": image_base64}
                })
            except Exception as e:
                print(f"❌ Error processing image in streaming: {str(e)}")
                # Continue processing other images

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "temperature": 0.1,
        "messages": [{"role": "user", "content": user_content if len(user_content) > 1 else enhanced_input}]
    }

    try:
        response = bedrock_runtime_client.invoke_model_with_response_stream(
            modelId=model_id,
            body=json.dumps(body)
        )

        for event in response['body']:
            if 'chunk' in event:
                chunk_data = json.loads(event['chunk']['bytes'])
                if chunk_data.get('type') == 'content_block_delta':
                    delta = chunk_data.get('delta', {})
                    if delta.get('type') == 'text_delta':
                        text = delta.get('text', '')
                        if text:
                            yield text

    except Exception as e:
        yield f"Error: {str(e)}"


def retrieve_and_generate_bedrock_stream(user_input: str, session_id: str, model_id: str, user_id: str, images: list = None, files: list = None):
    """Stream responses from Bedrock Knowledge Base or direct LLM"""
    # If attachments, go direct to LLM
    if (images and len(images) > 0) or (files and len(files) > 0):
        for chunk in invoke_direct_llm_bedrock_stream(user_input, model_id, session_id, user_id, images, files):
            yield chunk
        return

    # Classify intent to determine if KB should be queried
    from core.services.intent_classifier import classify_intent
    intent = classify_intent(user_input)
    if intent in ['GENERAL_CHAT', 'GREETING']:
        print(f"🎯 Intent: {intent} - Skipping KB, going directly to LLM")
        for chunk in invoke_direct_llm_bedrock_stream(user_input, model_id, session_id, user_id, images, files):
            yield chunk
        return

    # Map cross-region models to regional equivalents for KB
    kb_model_id = model_id
    if model_id.startswith("us."):
        kb_model_mapping = {
            "us.anthropic.claude-sonnet-4-20250514-v1:0": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "us.anthropic.claude-opus-4-20250514-v1:0": "anthropic.claude-3-opus-20240229-v1:0",
        }
        kb_model_id = kb_model_mapping.get(model_id, "anthropic.claude-3-5-sonnet-20241022-v2:0")

    model_arn = f'arn:aws:bedrock:{AWS_REGION}::foundation-model/{kb_model_id}'

    config = {
        'type': 'KNOWLEDGE_BASE',
        'knowledgeBaseConfiguration': {
            'knowledgeBaseId': KNOWLEDGE_BASE_ID,
            'modelArn': model_arn,
        }
    }

    if user_id:
        config['knowledgeBaseConfiguration']['retrievalConfiguration'] = {
            'vectorSearchConfiguration': {
                'filter': {'equals': {'key': 'user_id', 'value': user_id}}
            }
        }

    try:
        try:
            if session_id:
                response = bedrock_agent_runtime_client.retrieve_and_generate_stream(
                    input={'text': user_input},
                    retrieveAndGenerateConfiguration=config,
                    sessionId=session_id
                )
            else:
                response = bedrock_agent_runtime_client.retrieve_and_generate_stream(
                    input={'text': user_input},
                    retrieveAndGenerateConfiguration=config
                )
        except Exception as session_error:
            error_msg = str(session_error)
            if "Session with Id" in error_msg and "is not valid" in error_msg:
                response = bedrock_agent_runtime_client.retrieve_and_generate_stream(
                    input={'text': user_input},
                    retrieveAndGenerateConfiguration=config
                )
            else:
                raise

        for event in response['stream']:
            if 'chunk' in event:
                chunk_data = event['chunk']
                if 'bytes' in chunk_data:
                    chunk_json = json.loads(chunk_data['bytes'])
                    if 'outputText' in chunk_json:
                        yield chunk_json['outputText']
            elif 'output' in event:
                output = event['output']
                if 'text' in output:
                    yield output['text']

    except Exception as e:
        print(f"❌ KB streaming error: {e}, falling back to direct LLM")
        for chunk in invoke_direct_llm_bedrock_stream(user_input, model_id, session_id, user_id, images, files):
            yield chunk


def retrieve_and_generate_bedrock(user_input: str, session_id: str, model_id: str, user_id: str, images: list = None, files: list = None) -> str:
    """Query Bedrock Knowledge Base directly (non-streaming)"""
    # If attachments, go direct to LLM
    if (images and len(images) > 0) or (files and len(files) > 0):
        return invoke_direct_llm_bedrock(user_input, model_id, session_id, user_id, images, files)

    # Classify intent to determine if KB should be queried
    from core.services.intent_classifier import classify_intent
    intent = classify_intent(user_input)
    if intent in ['GENERAL_CHAT', 'GREETING']:
        print(f"🎯 Intent: {intent} - Skipping KB, going directly to LLM")
        return invoke_direct_llm_bedrock(user_input, model_id, session_id, user_id, images, files)

    # Map cross-region models for KB
    kb_model_id = model_id
    if model_id.startswith("us."):
        kb_model_mapping = {
            "us.anthropic.claude-sonnet-4-20250514-v1:0": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "us.anthropic.claude-opus-4-20250514-v1:0": "anthropic.claude-3-opus-20240229-v1:0",
        }
        kb_model_id = kb_model_mapping.get(model_id, "anthropic.claude-3-5-sonnet-20241022-v2:0")

    model_arn = f'arn:aws:bedrock:{AWS_REGION}::foundation-model/{kb_model_id}'

    config = {
        'knowledgeBaseConfiguration': {
            'knowledgeBaseId': KNOWLEDGE_BASE_ID,
            'modelArn': model_arn,
        },
        'type': 'KNOWLEDGE_BASE'
    }

    if user_id:
        config['knowledgeBaseConfiguration']['retrievalConfiguration'] = {
            'vectorSearchConfiguration': {
                'filter': {'equals': {'key': 'user_id', 'value': user_id}}
            }
        }

    try:
        if session_id:
            response = bedrock_agent_runtime_client.retrieve_and_generate(
                input={'text': user_input},
                retrieveAndGenerateConfiguration=config,
                sessionId=session_id
            )
        else:
            response = bedrock_agent_runtime_client.retrieve_and_generate(
                input={'text': user_input},
                retrieveAndGenerateConfiguration=config
            )

        # Check if response is insufficient
        if should_fallback_to_llm(response, user_input):
            return invoke_direct_llm_bedrock(user_input, model_id, session_id, user_id, images, files)

        return response['output']['text']

    except Exception as e:
        print(f"Knowledge base error: {str(e)}")
        return invoke_direct_llm_bedrock(user_input, model_id, session_id, user_id, images, files)
