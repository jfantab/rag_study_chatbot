"""
PDF Processing Module for Hybrid PDF Processing
Provides PDF hash/fingerprinting, chunking, and knowledge base management
"""
import hashlib
import base64
import json
import uuid
import boto3
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from botocore.exceptions import ClientError
import io
import PyPDF2
from constants import BEDROCK_API_URL

class PDFProcessor:
    """Handles PDF processing operations including hashing, chunking, and KB management"""

    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.s3_client = boto3.client('s3')
        self.textract_client = boto3.client('textract')

        # Initialize document status table
        self._ensure_document_status_table()

    def _ensure_document_status_table(self):
        """Create document_status table if it doesn't exist"""
        try:
            table_name = 'DocumentStatus'

            # Check if table exists
            try:
                self.dynamodb.Table(table_name).table_status
                print(f"✅ DocumentStatus table already exists")
                return
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceNotFoundException':
                    raise e

            print("🔧 Creating DocumentStatus table...")

            # Create the table
            table = self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'pdf_hash', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'pdf_hash', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST'
            )

            # Wait for table to be created
            table.wait_until_exists()
            print("✅ DocumentStatus table created successfully")

        except Exception as e:
            print(f"❌ Error creating DocumentStatus table: {str(e)}")
            raise

    def calculate_pdf_hash(self, pdf_file_data) -> str:
        """
        Calculate a unique hash for PDF content
        Uses SHA-256 hash of the PDF content for deduplication
        """
        try:
            # Extract PDF content from various input formats
            if isinstance(pdf_file_data, dict) and 'content' in pdf_file_data:
                # File comes from mobile app as base64
                pdf_content = base64.b64decode(pdf_file_data['content'])
            elif isinstance(pdf_file_data, bytes):
                pdf_content = pdf_file_data
            else:
                raise ValueError("Invalid PDF file data format for hashing")

            # Create SHA-256 hash of the PDF content
            pdf_hash = hashlib.sha256(pdf_content).hexdigest()
            return f"pdf_{pdf_hash[:32]}"  # Truncate for readability
        except Exception as e:
            print(f"❌ Error calculating PDF hash: {str(e)}")
            raise

    def get_pdf_size_tokens(self, pdf_file_data) -> int:
        """
        Estimate the number of tokens in a PDF
        Rough estimation: 1 token ≈ 4 characters
        """
        try:
            # Extract PDF content from various input formats
            if isinstance(pdf_file_data, dict) and 'content' in pdf_file_data:
                # File comes from mobile app as base64
                pdf_content = base64.b64decode(pdf_file_data['content'])
            elif isinstance(pdf_file_data, bytes):
                pdf_content = pdf_file_data
            else:
                raise ValueError("Invalid PDF file data format for token estimation")

            # Extract text using PyPDF2 for quick estimation
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()

            # Rough token estimation: 1 token ≈ 4 characters
            estimated_tokens = len(text) // 4
            return estimated_tokens
        except Exception as e:
            print(f"⚠️ Error estimating PDF tokens, using size fallback: {str(e)}")
            # Fallback: estimate based on file size (very rough)
            if isinstance(pdf_file_data, dict):
                # Estimate from base64 content size
                content_size = len(pdf_file_data.get('content', '')) * 3 // 4  # base64 to bytes
                return content_size // 20
            elif isinstance(pdf_file_data, bytes):
                return len(pdf_file_data) // 20
            else:
                return 1000  # Default fallback

    def check_kb_document_exists(self, pdf_hash: str) -> Dict[str, Any]:
        """
        Check if a PDF document already exists in the knowledge base
        Returns document status and metadata
        """
        try:
            table = self.dynamodb.Table('DocumentStatus')

            response = table.get_item(Key={'pdf_hash': pdf_hash})

            if 'Item' in response:
                doc_status = response['Item']
                return {
                    'exists': True,
                    'status': doc_status.get('status', 'unknown'),
                    'kb_document_id': doc_status.get('kb_document_id'),
                    'upload_timestamp': doc_status.get('upload_timestamp'),
                    'file_metadata': doc_status.get('file_metadata', {})
                }
            else:
                return {'exists': False}

        except Exception as e:
            print(f"❌ Error checking KB document existence: {str(e)}")
            return {'exists': False, 'error': str(e)}

    def save_document_status(self, pdf_hash: str, status: str,
                           file_metadata: Dict, kb_document_id: Optional[str] = None):
        """
        Save or update document processing status
        Status: 'uploading', 'indexed', 'failed'
        """
        try:
            table = self.dynamodb.Table('DocumentStatus')

            item = {
                'pdf_hash': pdf_hash,
                'status': status,
                'upload_timestamp': datetime.now().isoformat(),
                'file_metadata': file_metadata
            }

            if kb_document_id:
                item['kb_document_id'] = kb_document_id

            table.put_item(Item=item)
            print(f"✅ Saved document status: {pdf_hash} -> {status}")

        except Exception as e:
            print(f"❌ Error saving document status: {str(e)}")
            raise

    def extract_pdf_text_with_textract(self, pdf_content: bytes) -> str:
        """
        Extract text from PDF using PyPDF2 as primary method, Textract as fallback
        """
        try:
            # Try PyPDF2 first as it's more reliable for text-based PDFs
            text = self._extract_text_with_pypdf2(pdf_content)

            # If PyPDF2 extracted good text, use it
            if text and len(text.strip()) > 50:  # Reasonable amount of text
                print(f"✅ PyPDF2 extraction successful: {len(text)} characters")
                return text

            # If PyPDF2 didn't get much text, try Textract for scanned PDFs
            print(f"⚠️ PyPDF2 extracted limited text ({len(text)} chars), trying Textract...")

            # For small PDFs, use synchronous detection
            if len(pdf_content) < 5 * 1024 * 1024:  # 5MB limit for sync
                response = self.textract_client.detect_document_text(
                    Document={'Bytes': pdf_content}
                )

                # Extract text from response
                text_blocks = []
                for block in response.get('Blocks', []):
                    if block['BlockType'] == 'LINE':
                        text_blocks.append(block['Text'])

                textract_text = '\n'.join(text_blocks)
                if textract_text and len(textract_text.strip()) > len(text.strip()):
                    print(f"✅ Textract extraction better: {len(textract_text)} characters")
                    return textract_text
                else:
                    print(f"✅ Using PyPDF2 result: {len(text)} characters")
                    return text
            else:
                # For larger PDFs, use PyPDF2 result
                print(f"📄 Large PDF, using PyPDF2 result: {len(text)} characters")
                return text

        except Exception as e:
            print(f"⚠️ Textract extraction failed, using PyPDF2 fallback: {str(e)}")
            return self._extract_text_with_pypdf2(pdf_content)

    def _extract_text_with_pypdf2(self, pdf_content: bytes) -> str:
        """Fallback text extraction using PyPDF2"""
        try:
            # Validate PDF content first
            if not pdf_content or len(pdf_content) < 100:
                print(f"❌ Invalid PDF content: too small ({len(pdf_content)} bytes)")
                return ""

            # Check for PDF header
            if not pdf_content.startswith(b'%PDF'):
                print(f"❌ Invalid PDF content: missing PDF header")
                return ""

            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))

            # Check if PDF is encrypted
            if pdf_reader.is_encrypted:
                print(f"⚠️ PDF is encrypted, attempting to decrypt...")
                try:
                    pdf_reader.decrypt("")  # Try with empty password
                except:
                    print(f"❌ Cannot decrypt PDF")
                    return "This PDF is password-protected and cannot be processed."

            text_pages = []
            total_pages = len(pdf_reader.pages)
            print(f"📄 Processing {total_pages} pages with PyPDF2...")

            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text_pages.append(f"=== Page {page_num + 1} ===\n{page_text}")
                    else:
                        print(f"⚠️ Page {page_num + 1} contains no extractable text")
                except Exception as e:
                    print(f"⚠️ Error extracting page {page_num + 1}: {str(e)}")

            if not text_pages:
                return "This PDF appears to contain no extractable text. It may be a scanned document or contain only images."

            extracted_text = '\n\n'.join(text_pages)
            print(f"✅ PyPDF2 extracted {len(extracted_text)} characters from {len(text_pages)} pages")
            return extracted_text

        except Exception as e:
            print(f"❌ PyPDF2 extraction failed: {str(e)}")
            return f"Error processing PDF: {str(e)}"

    def chunk_pdf_intelligently(self, text: str, chunk_size: int = 8000,
                               overlap: int = 200) -> List[str]:
        """
        Intelligent chunking that preserves document structure
        """
        try:
            if not text.strip():
                return []

            # Split by pages first
            page_sections = text.split('=== Page ')
            chunks = []
            current_chunk = ""

            for section in page_sections:
                if not section.strip():
                    continue

                # Add page marker back if this isn't the first section
                if section != page_sections[0]:
                    section = '=== Page ' + section

                # Split long pages by paragraphs
                paragraphs = section.split('\n\n')

                for paragraph in paragraphs:
                    paragraph = paragraph.strip()
                    if not paragraph:
                        continue

                    # Check if adding this paragraph would exceed chunk size
                    if len(current_chunk) + len(paragraph) + 2 > chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            # Start new chunk with overlap
                            if overlap > 0 and len(current_chunk) > overlap:
                                current_chunk = current_chunk[-overlap:] + '\n\n' + paragraph
                            else:
                                current_chunk = paragraph
                        else:
                            # Single paragraph is too long, split by sentences
                            sentences = paragraph.split('. ')
                            for sentence in sentences:
                                if len(current_chunk) + len(sentence) + 2 > chunk_size:
                                    if current_chunk:
                                        chunks.append(current_chunk.strip())
                                        current_chunk = sentence
                                    else:
                                        # Even single sentence is too long, force split
                                        chunks.append(sentence[:chunk_size])
                                        current_chunk = sentence[chunk_size:]
                                else:
                                    current_chunk += '. ' + sentence if current_chunk else sentence
                    else:
                        current_chunk += '\n\n' + paragraph if current_chunk else paragraph

            # Add final chunk
            if current_chunk.strip():
                chunks.append(current_chunk.strip())

            print(f"✅ Created {len(chunks)} intelligent chunks from PDF text")
            return chunks

        except Exception as e:
            print(f"❌ Error in intelligent chunking: {str(e)}")
            # Fallback to simple chunking
            return self._simple_chunk(text, chunk_size, overlap)

    def _simple_chunk(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Simple fallback chunking method"""
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap

        return chunks

    def select_relevant_chunks(self, chunks: List[str], user_query: str,
                             max_chunks: int = 10) -> List[str]:
        """
        Select most relevant chunks based on user query
        Simple keyword-based relevance for now
        """
        try:
            query_words = set(user_query.lower().split())

            # Score chunks based on keyword overlap
            chunk_scores = []
            for i, chunk in enumerate(chunks):
                chunk_words = set(chunk.lower().split())
                overlap_score = len(query_words.intersection(chunk_words))
                chunk_scores.append((overlap_score, i, chunk))

            # Sort by score and return top chunks
            chunk_scores.sort(key=lambda x: x[0], reverse=True)
            selected_chunks = [chunk for _, _, chunk in chunk_scores[:max_chunks]]

            print(f"✅ Selected {len(selected_chunks)} most relevant chunks")
            return selected_chunks

        except Exception as e:
            print(f"⚠️ Error in chunk selection, returning all chunks: {str(e)}")
            return chunks[:max_chunks]

    def process_chunks_with_bedrock(self, chunks: List[str], user_query: str,
                                  user_id: str) -> List[str]:
        """
        Process chunks in parallel using Bedrock API
        """
        try:
            responses = []

            for i, chunk in enumerate(chunks):
                try:
                    # Create a context-aware query for each chunk
                    chunk_query = f"""Based on this document section, answer the user's question: "{user_query}"

Document section {i+1}:
{chunk}

Please provide a specific answer based only on the information in this section. If the section doesn't contain relevant information, respond with "This section doesn't contain relevant information for the query."
"""

                    # Call Bedrock API
                    payload = {
                        "question": chunk_query,
                        "sessionId": str(uuid.uuid4()),
                        "model_id": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                        "filters": {
                            "equals": {
                                "key": "user_id",
                                "value": user_id
                            }
                        }
                    }

                    response = requests.post(
                        BEDROCK_API_URL,
                        headers={'Content-Type': 'application/json'},
                        data=json.dumps(payload),
                        timeout=30
                    )

                    if response.ok:
                        result = response.json()
                        answer = result.get('body', {}).get('answer', '')
                        if answer and "doesn't contain relevant information" not in answer:
                            responses.append(answer)

                except Exception as chunk_error:
                    print(f"⚠️ Error processing chunk {i+1}: {str(chunk_error)}")
                    continue

            print(f"✅ Processed {len(responses)} chunks successfully")
            return responses

        except Exception as e:
            print(f"❌ Error processing chunks with Bedrock: {str(e)}")
            return []

    def consolidate_responses(self, chunk_responses: List[str], user_query: str) -> str:
        """
        Consolidate multiple chunk responses into a coherent answer
        """
        try:
            if not chunk_responses:
                return "I couldn't find relevant information in the document to answer your question."

            if len(chunk_responses) == 1:
                return chunk_responses[0]

            # Create consolidation prompt
            consolidation_query = f"""Please consolidate these responses into a single, coherent answer for the question: "{user_query}"

Individual responses:
{chr(10).join([f"{i+1}. {response}" for i, response in enumerate(chunk_responses)])}

Provide a comprehensive answer that combines the relevant information, removes duplicates, and presents it in a clear, organized manner. If there are contradictions, note them appropriately.
"""

            # Use Bedrock to consolidate
            payload = {
                "question": consolidation_query,
                "sessionId": str(uuid.uuid4()),
                "model_id": "us.anthropic.claude-sonnet-4-20250514-v1:0"
            }

            response = requests.post(
                BEDROCK_API_URL,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(payload),
                timeout=30
            )

            if response.ok:
                result = response.json()
                consolidated_answer = result.get('body', {}).get('answer', '')
                if consolidated_answer:
                    return consolidated_answer

            # Fallback: simple concatenation
            return self._simple_consolidation(chunk_responses, user_query)

        except Exception as e:
            print(f"⚠️ Error consolidating responses, using fallback: {str(e)}")
            return self._simple_consolidation(chunk_responses, user_query)

    def _simple_consolidation(self, responses: List[str], user_query: str) -> str:
        """Simple fallback consolidation"""
        return f"Based on the document, here's what I found regarding '{user_query}':\n\n" + \
               "\n\n".join([f"• {response}" for response in responses])

    def query_knowledge_base(self, user_query: str, pdf_hash: str, user_id: str) -> str:
        """
        Query the knowledge base for a specific document
        """
        try:
            # Get document info
            doc_info = self.check_kb_document_exists(pdf_hash)

            if not doc_info.get('exists') or doc_info.get('status') != 'indexed':
                raise Exception("Document not available in knowledge base")

            kb_document_id = doc_info.get('kb_document_id')

            # Query knowledge base with document filter
            payload = {
                "question": user_query,
                "sessionId": str(uuid.uuid4()),
                "model_id": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                "filters": {
                    "equals": {
                        "key": "document_id",
                        "value": kb_document_id
                    }
                }
            }

            response = requests.post(
                BEDROCK_API_URL,
                headers={'Content-Type': 'application/json'},
                data=json.dumps(payload),
                timeout=30
            )

            if response.ok:
                result = response.json()
                return result.get('body', {}).get('answer', 'No answer found in knowledge base.')
            else:
                raise Exception(f"KB query failed: {response.status_code}")

        except Exception as e:
            print(f"❌ Error querying knowledge base: {str(e)}")
            raise

    def start_kb_upload_background(self, pdf_file_data, pdf_hash: str,
                                 file_metadata: Dict):
        """
        Start background knowledge base upload process
        In a production system, this would trigger an async job
        """
        try:
            # Update status to uploading
            self.save_document_status(pdf_hash, 'uploading', file_metadata)

            # In a real implementation, this would:
            # 1. Upload PDF to S3 with proper naming
            # 2. Trigger Lambda function or SQS message for KB processing
            # 3. KB processing would update the status when complete

            # For now, we'll mark as upload initiated
            print(f"🚀 Started background KB upload for document: {pdf_hash}")

            # TODO: Implement actual async KB upload
            # This would involve:
            # - S3 upload with metadata
            # - SQS message or Lambda trigger
            # - KB sync job processing
            # - Status update when complete

        except Exception as e:
            print(f"❌ Error starting KB upload: {str(e)}")
            self.save_document_status(pdf_hash, 'failed', file_metadata)
            raise