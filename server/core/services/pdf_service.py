"""
PDF Processing Service

Handles all PDF-related processing operations including:
- Hybrid processing (immediate response + background indexing)
- Immediate chunking for fast responses
- Partial processing for large documents
"""

import base64
from datetime import datetime
from core.services.pdf_processing import PDFProcessor


def process_pdf_hybrid(user_message, pdf_file_data, user_query, user_id):
    """
    Hybrid PDF processing: immediate chunking response + background KB building
    """
    try:
        pdf_processor = PDFProcessor()

        # Calculate PDF hash for deduplication
        pdf_hash = pdf_processor.calculate_pdf_hash(pdf_file_data)
        print(f"📋 PDF hash calculated: {pdf_hash}")

        # Check if PDF already exists in KB
        kb_status = pdf_processor.check_kb_document_exists(pdf_hash)

        if kb_status.get('exists') and kb_status.get('status') == 'indexed':
            print(f"✅ PDF found in KB, using knowledge base retrieval")
            # Fast path: Use KB retrieval
            try:
                response = pdf_processor.query_knowledge_base(user_query, pdf_hash, user_id)
                return response
            except Exception as kb_error:
                print(f"⚠️ KB query failed, falling back to chunking: {str(kb_error)}")
                # Fall through to chunking if KB query fails

        # Hybrid path: Immediate chunking + background KB upload
        pdf_size_tokens = pdf_processor.get_pdf_size_tokens(pdf_file_data)
        print(f"📊 Estimated PDF size: {pdf_size_tokens} tokens")

        # Create file metadata
        file_metadata = {
            'filename': pdf_file_data.get('name', 'document.pdf'),
            'size': len(pdf_file_data) if isinstance(pdf_file_data, bytes) else pdf_file_data.get('size', 0),
            'upload_date': datetime.now().isoformat(),
            'user_id': user_id,
            'estimated_tokens': pdf_size_tokens
        }

        # UNIFIED HYBRID APPROACH FOR ALL PDFS
        print(f"📚 Using unified hybrid approach for all PDFs.")

        # Start KB upload in background (if not already uploading/indexed)
        if not kb_status.get('exists') or kb_status.get('status') not in ['uploading', 'indexed']:
            try:
                print(f"🚀 Initiating background indexing for pdf_hash: {pdf_hash}")
                pdf_processor.start_kb_upload_background(pdf_file_data, pdf_hash, file_metadata)
            except Exception as bg_error:
                print(f"⚠️ Background upload failed: {str(bg_error)}")

        # Process the document for an immediate response.
        # For small documents, this will likely process the whole file.
        # For large documents, it will process the first part.
        print(f"⚡ Generating immediate response for pdf_hash: {pdf_hash}")
        immediate_response = process_pdf_chunks_partial(pdf_file_data, user_query, user_id, max_tokens=30000)

        # Add a status message informing the user about the background indexing.
        # This is now consistent for all PDFs.
        enhanced_response = f"""{immediate_response}

📋 *Note: This response is based on an initial analysis of your document. The complete document is being indexed in the background for future, more comprehensive queries.*"""

        return enhanced_response

    except Exception as e:
        print(f"❌ Error in hybrid PDF processing: {str(e)}")
        raise


def process_pdf_chunks_immediate(pdf_file_data, user_query, user_id):
    """
    Process PDF chunks immediately for quick response
    """
    try:
        pdf_processor = PDFProcessor()

        # Extract PDF content from file data
        if isinstance(pdf_file_data, dict) and 'content' in pdf_file_data:
            # File comes from mobile app as base64
            pdf_content = base64.b64decode(pdf_file_data['content'])
        elif isinstance(pdf_file_data, bytes):
            pdf_content = pdf_file_data
        else:
            raise ValueError("Invalid PDF file data format")

        # Extract text with Textract
        print(f"🔍 Extracting text from PDF...")
        full_text = pdf_processor.extract_pdf_text_with_textract(pdf_content)

        if not full_text.strip():
            return "I couldn't extract readable text from this PDF. Please ensure it's a text-based PDF and try again."

        # Smart chunking based on document structure
        print(f"✂️ Creating intelligent chunks...")
        chunks = pdf_processor.chunk_pdf_intelligently(full_text, chunk_size=8000, overlap=200)

        if not chunks:
            return "I couldn't process the content of this PDF. Please try again with a different document."

        # Query-aware chunk selection
        print(f"🎯 Selecting relevant chunks for query...")
        relevant_chunks = pdf_processor.select_relevant_chunks(chunks, user_query, max_chunks=10)

        # Process chunks in parallel
        print(f"🚀 Processing {len(relevant_chunks)} chunks with Bedrock...")
        chunk_responses = pdf_processor.process_chunks_with_bedrock(relevant_chunks, user_query, user_id)

        if not chunk_responses:
            return "I couldn't find relevant information in the document to answer your question. Please try rephrasing your question or checking if the document contains the information you're looking for."

        # Consolidate responses
        print(f"🔗 Consolidating responses...")
        final_response = pdf_processor.consolidate_responses(chunk_responses, user_query)

        return final_response

    except Exception as e:
        print(f"❌ Error in immediate PDF processing: {str(e)}")
        return f"I encountered an error processing your PDF: {str(e)}. Please try again."


def process_pdf_chunks_partial(pdf_file_data, user_query, user_id, max_tokens=30000):
    """
    Process only first portion of PDF for immediate response
    """
    try:
        pdf_processor = PDFProcessor()

        # Extract PDF content
        if isinstance(pdf_file_data, dict) and 'content' in pdf_file_data:
            pdf_content = base64.b64decode(pdf_file_data['content'])
        elif isinstance(pdf_file_data, bytes):
            pdf_content = pdf_file_data
        else:
            raise ValueError("Invalid PDF file data format")

        # Extract text
        print(f"🔍 Extracting text from PDF (partial)...")
        full_text = pdf_processor.extract_pdf_text_with_textract(pdf_content)

        if not full_text.strip():
            return "I couldn't extract readable text from this PDF."

        # Truncate to max_tokens for partial processing
        # Rough estimation: 1 token ≈ 4 characters
        max_chars = max_tokens * 4
        if len(full_text) > max_chars:
            partial_text = full_text[:max_chars]
            # Try to cut at a reasonable boundary
            last_sentence = partial_text.rfind('. ')
            if last_sentence > max_chars * 0.8:  # If we can cut at a sentence boundary
                partial_text = partial_text[:last_sentence + 1]
        else:
            partial_text = full_text

        # Create chunks from partial text
        chunks = pdf_processor.chunk_pdf_intelligently(partial_text, chunk_size=6000, overlap=150)

        # Select relevant chunks
        relevant_chunks = pdf_processor.select_relevant_chunks(chunks, user_query, max_chunks=8)

        # Process chunks
        chunk_responses = pdf_processor.process_chunks_with_bedrock(relevant_chunks, user_query, user_id)

        if not chunk_responses:
            return "I couldn't find relevant information in the first part of the document. The full document is being processed for future queries."

        # Consolidate responses
        final_response = pdf_processor.consolidate_responses(chunk_responses, user_query)

        return final_response

    except Exception as e:
        print(f"❌ Error in partial PDF processing: {str(e)}")
        return f"I encountered an error processing your PDF: {str(e)}"
