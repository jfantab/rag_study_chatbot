"""
PDF processing utilities for chat operations
Handles PDF-specific processing and hybrid approaches
"""
import boto3
from core.services.pdf_processing import PDFProcessor
from core.services.pdf_service import process_pdf_hybrid
from core.aws.dynamodb_service import get_chat_pk, get_chat_sk


def process_pdf_with_hybrid(question, pdf_files, msg_id, user_id):
    """
    Process PDF files using hybrid approach

    Args:
        question: User's question
        pdf_files: List of PDF file data
        msg_id: Message/session ID
        user_id: User ID

    Returns:
        str: Answer from PDF processing
    """
    print(f"Detected {len(pdf_files)} PDF file(s), using hybrid processing")

    # We will only process the first PDF and associate it with the chat session.
    first_pdf = pdf_files[0]

    try:
        answer = process_pdf_hybrid(question, first_pdf, question, user_id)

        # Calculate the hash of the processed PDF to associate with the session
        pdf_processor = PDFProcessor()
        pdf_hash = pdf_processor.calculate_pdf_hash(first_pdf)

        # Save the PDF hash to the chat session metadata in DynamoDB
        print(f"Associating pdf_hash: {pdf_hash} with session_id: {msg_id}")
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table('ChatSessions')
        table.update_item(
            Key={
                'PK': get_chat_pk(user_id),
                'SK': get_chat_sk(msg_id)
            },
            UpdateExpression="set associated_pdf_hash = :h",
            ExpressionAttributeValues={
                ':h': pdf_hash
            },
        )

        # If multiple PDFs were uploaded, inform the user only the first was processed.
        if len(pdf_files) > 1:
            answer = f"""{answer}

Note: I processed the first PDF file ({first_pdf.get('name', 'document.pdf')}). You uploaded {len(pdf_files)} PDF files total. Please ask separate questions for each document if you need information from the others."""

        return answer

    except Exception as pdf_error:
        print(f"PDF hybrid processing failed: {str(pdf_error)}")
        raise  # Re-raise to be handled by caller
