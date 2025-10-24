"""
Document processing utilities for extracting text from PDFs and other document types
Uses AWS Textract for PDF processing
"""
import base64
import boto3
from constants import AWS_REGION

# Initialize Textract client
textract_client = boto3.client('textract', region_name=AWS_REGION)


def extract_pdf_text_with_textract(base64_content: str, file_name: str) -> str:
    """
    Extract text from PDF using AWS Textract

    Args:
        base64_content: Base64 encoded PDF content
        file_name: Name of the PDF file

    Returns:
        Extracted text or error message
    """
    try:
        pdf_bytes = base64.b64decode(base64_content)
        file_size_mb = len(pdf_bytes) / (1024 * 1024)

        if file_size_mb > 10:
            return f"[PDF file '{file_name}' is too large ({file_size_mb:.2f} MB) for text extraction. Maximum size is 10MB.]"

        response = textract_client.detect_document_text(Document={'Bytes': pdf_bytes})

        extracted_text = []
        for block in response['Blocks']:
            if block['BlockType'] == 'LINE':
                extracted_text.append(block['Text'])

        full_text = '\n'.join(extracted_text)
        return full_text.strip() if full_text.strip() else f"[PDF file '{file_name}' appears to contain no extractable text content]"

    except Exception as e:
        return f"[PDF '{file_name}' could not be processed: {str(e)}]"


def extract_text_from_document(base64_content: str, file_name: str, file_type: str) -> str:
    """
    Extract text from various document types

    Args:
        base64_content: Base64 encoded file content
        file_name: Name of the file
        file_type: MIME type or file extension

    Returns:
        Extracted text or error message
    """
    try:
        if file_type.lower() in ['application/pdf', 'pdf']:
            return extract_pdf_text_with_textract(base64_content, file_name)

        elif file_type.lower() in ['text/plain', 'txt', 'text']:
            try:
                return base64.b64decode(base64_content).decode('utf-8')
            except UnicodeDecodeError:
                return f"[Text file '{file_name}' contains non-UTF-8 content]"

        elif any(doc_type in file_type.lower() for doc_type in ['word', 'document', 'rtf', 'txt']):
            try:
                return base64.b64decode(base64_content).decode('utf-8')
            except UnicodeDecodeError:
                return f"[Document file '{file_name}' (type: {file_type}) contains binary content that cannot be processed as text]"

        else:
            return f"[File type '{file_type}' is not supported for text extraction from '{file_name}']"

    except Exception as e:
        return f"[Error processing file '{file_name}': {str(e)}]"
