import os
import base64
import json
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Dict, List, Any, Optional


class AESMessageEncryption:
    def __init__(self, encryption_key: str = None):
        """
        Initialize AES encryption with a key from environment or provided key
        """
        # Check if running in production mode
        is_production = os.getenv('ENVIRONMENT', 'development').lower() == 'production'

        if encryption_key:
            self.key = encryption_key.encode()
        else:
            # Use environment variable or fail in production
            env_key = os.getenv('CHAT_ENCRYPTION_KEY')
            if env_key:
                self.key = env_key.encode()
            else:
                if is_production:
                    raise ValueError(
                        "❌ CRITICAL: CHAT_ENCRYPTION_KEY environment variable is required in production. "
                        "Set this variable to ensure data persistence across server restarts."
                    )
                else:
                    # Only allow temporary key in development
                    self.key = Fernet.generate_key()
                    print("⚠️  WARNING: No CHAT_ENCRYPTION_KEY found. Generated temporary key for DEVELOPMENT only.")
                    print("⚠️  Set CHAT_ENCRYPTION_KEY environment variable for data persistence.")

        # Get salt from environment or use per-deployment salt
        salt_string = os.getenv('ENCRYPTION_SALT', 'default_app_salt_v1')
        salt = salt_string.encode()[:16].ljust(16, b'0')  # Ensure 16 bytes

        # Derive Fernet key from the provided key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        fernet_key = base64.urlsafe_b64encode(kdf.derive(self.key))
        self.cipher_suite = Fernet(fernet_key)

    def encrypt_text(self, text: str) -> str:
        """
        Encrypt a text string and return base64 encoded encrypted data
        """
        try:
            if not text:
                return text
            encrypted_data = self.cipher_suite.encrypt(text.encode('utf-8'))
            return base64.b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            print(f"❌ Error encrypting text: {str(e)}")
            raise

    def decrypt_text(self, encrypted_text: str) -> str:
        """
        Decrypt a base64 encoded encrypted text string
        """
        try:
            if not encrypted_text:
                return encrypted_text
            encrypted_data = base64.b64decode(encrypted_text.encode('utf-8'))
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            return decrypted_data.decode('utf-8')
        except Exception as e:
            print(f"❌ Error decrypting text: {str(e)}")
            raise

    def encrypt_message_content(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt the content field of a message while preserving structure
        """
        try:
            encrypted_message = message.copy()

            # Encrypt the main content
            if 'content' in encrypted_message and encrypted_message['content']:
                encrypted_message['content'] = self.encrypt_text(encrypted_message['content'])
                encrypted_message['encrypted'] = True

            # Encrypt image URLs if present
            if 'image_urls' in encrypted_message and encrypted_message['image_urls']:
                encrypted_urls = []
                for url in encrypted_message['image_urls']:
                    encrypted_urls.append(self.encrypt_text(url))
                encrypted_message['image_urls'] = encrypted_urls

            # Encrypt any file paths or file content
            if 'file_path' in encrypted_message and encrypted_message['file_path']:
                encrypted_message['file_path'] = self.encrypt_text(encrypted_message['file_path'])

            if 'file_content' in encrypted_message and encrypted_message['file_content']:
                encrypted_message['file_content'] = self.encrypt_text(encrypted_message['file_content'])

            return encrypted_message
        except Exception as e:
            print(f"❌ Error encrypting message content: {str(e)}")
            raise

    def decrypt_message_content(self, encrypted_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt the content field of a message while preserving structure
        """
        try:
            decrypted_message = encrypted_message.copy()

            # Only decrypt if the message was encrypted
            if encrypted_message.get('encrypted', False):
                # Decrypt the main content
                if 'content' in decrypted_message and decrypted_message['content']:
                    decrypted_message['content'] = self.decrypt_text(decrypted_message['content'])

                # Decrypt image URLs if present
                if 'image_urls' in decrypted_message and decrypted_message['image_urls']:
                    decrypted_urls = []
                    for url in decrypted_message['image_urls']:
                        decrypted_urls.append(self.decrypt_text(url))
                    decrypted_message['image_urls'] = decrypted_urls

                # Decrypt any file paths or file content
                if 'file_path' in decrypted_message and decrypted_message['file_path']:
                    decrypted_message['file_path'] = self.decrypt_text(decrypted_message['file_path'])

                if 'file_content' in decrypted_message and decrypted_message['file_content']:
                    decrypted_message['file_content'] = self.decrypt_text(decrypted_message['file_content'])

                # Remove encryption flag
                decrypted_message.pop('encrypted', None)

            return decrypted_message
        except Exception as e:
            print(f"❌ Error decrypting message content: {str(e)}")
            # Return original message if decryption fails
            return encrypted_message

    def encrypt_chat_history(self, chat_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Encrypt all message content in chat history while preserving structure
        """
        try:
            encrypted_history = []
            for message in chat_history:
                encrypted_message = self.encrypt_message_content(message)
                encrypted_history.append(encrypted_message)
            return encrypted_history
        except Exception as e:
            print(f"❌ Error encrypting chat history: {str(e)}")
            raise

    def decrypt_chat_history(self, encrypted_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Decrypt all message content in chat history while preserving structure
        """
        try:
            decrypted_history = []
            for message in encrypted_history:
                decrypted_message = self.decrypt_message_content(message)
                decrypted_history.append(decrypted_message)
            return decrypted_history
        except Exception as e:
            print(f"❌ Error decrypting chat history: {str(e)}")
            # Return original history if decryption fails
            return encrypted_history

    def encrypt_file_data(self, file_data: bytes) -> str:
        """
        Encrypt binary file data and return base64 encoded result
        """
        try:
            encrypted_data = self.cipher_suite.encrypt(file_data)
            return base64.b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            print(f"❌ Error encrypting file data: {str(e)}")
            raise

    def decrypt_file_data(self, encrypted_file_data) -> bytes:
        """
        Decrypt base64 encoded file data and return original bytes
        Args:
            encrypted_file_data: Either base64 string or bytes data
        """
        try:
            # Handle both string (base64) and bytes input
            if isinstance(encrypted_file_data, str):
                # Base64 string - decode it
                encrypted_data = base64.b64decode(encrypted_file_data.encode('utf-8'))
            elif isinstance(encrypted_file_data, bytes):
                # Already bytes - use directly
                encrypted_data = encrypted_file_data
            else:
                raise ValueError(f"Unsupported data type: {type(encrypted_file_data)}")

            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            return decrypted_data
        except Exception as e:
            print(f"❌ Error decrypting file data: {str(e)}")
            raise

    def encrypt_chat_name(self, chat_name: str) -> str:
        """
        Encrypt a chat name for database storage and return base64 encoded encrypted data
        """
        try:
            if not chat_name:
                return chat_name
            return self.encrypt_text(chat_name)
        except Exception as e:
            print(f"❌ Error encrypting chat name: {str(e)}")
            raise

    def decrypt_chat_name(self, encrypted_chat_name: str) -> str:
        """
        Decrypt a base64 encoded encrypted chat name from database storage
        """
        try:
            if not encrypted_chat_name:
                return encrypted_chat_name
            return self.decrypt_text(encrypted_chat_name)
        except Exception as e:
            print(f"❌ Error decrypting chat name: {str(e)}")
            raise


# Global encryption instance
encryption = AESMessageEncryption()