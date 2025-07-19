"""Encryption utilities for credential storage."""

import os
import base64
from typing import Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)


class CredentialEncryption:
    """Handles encryption/decryption of credentials."""
    
    def __init__(self, key: Optional[str] = None):
        """Initialize encryption with a key.
        
        Args:
            key: Encryption key. If not provided, will check environment
                 or generate a new one.
        """
        self.cipher = self._get_cipher(key)
    
    def _get_cipher(self, key: Optional[str] = None) -> Fernet:
        """Get or create encryption cipher.
        
        Args:
            key: Optional encryption key
            
        Returns:
            Fernet cipher instance
        """
        if key:
            # Use provided key
            fernet_key = self._derive_key(key)
        else:
            # Check environment for key
            env_key = os.environ.get('AWS_AGENT_ENCRYPTION_KEY')
            if env_key:
                fernet_key = self._derive_key(env_key)
            else:
                # Generate new key (for demo/dev only)
                fernet_key = Fernet.generate_key()
                logger.warning(
                    "No encryption key found. Generated temporary key. "
                    "For production, set AWS_AGENT_ENCRYPTION_KEY environment variable."
                )
                # Save to a local file for development convenience
                key_file = os.path.expanduser('~/.aws_agent_key')
                try:
                    with open(key_file, 'wb') as f:
                        f.write(fernet_key)
                    os.chmod(key_file, 0o600)  # Restrict permissions
                    logger.info(f"Saved encryption key to {key_file}")
                except Exception as e:
                    logger.warning(f"Could not save encryption key: {e}")
        
        return Fernet(fernet_key)
    
    def _derive_key(self, password: str) -> bytes:
        """Derive a Fernet key from a password.
        
        Args:
            password: Password to derive key from
            
        Returns:
            Fernet-compatible key
        """
        # Use a fixed salt for simplicity (in production, store salt separately)
        salt = b'aws_agent_salt_v1'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt(self, data: Union[str, bytes]) -> str:
        """Encrypt data.
        
        Args:
            data: Data to encrypt (string or bytes)
            
        Returns:
            Base64-encoded encrypted data
        """
        if isinstance(data, str):
            data = data.encode()
        
        encrypted = self.cipher.encrypt(data)
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data.
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            
        Returns:
            Decrypted string
        """
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data") from e
    
    def encrypt_dict(self, data: dict) -> dict:
        """Encrypt sensitive fields in a dictionary.
        
        Args:
            data: Dictionary with potential sensitive data
            
        Returns:
            Dictionary with encrypted sensitive fields
        """
        encrypted_data = data.copy()
        sensitive_fields = [
            'aws_access_key_id', 'aws_secret_access_key', 'aws_session_token',
            'password', 'api_key', 'secret', 'token', 'key'
        ]
        
        for key, value in data.items():
            if any(field in key.lower() for field in sensitive_fields):
                if isinstance(value, str) and value:
                    encrypted_data[key] = f"ENC:{self.encrypt(value)}"
                    logger.debug(f"Encrypted field: {key}")
            elif isinstance(value, dict):
                # Recursively encrypt nested dictionaries
                encrypted_data[key] = self.encrypt_dict(value)
        
        return encrypted_data
    
    def decrypt_dict(self, data: dict) -> dict:
        """Decrypt encrypted fields in a dictionary.
        
        Args:
            data: Dictionary with encrypted fields
            
        Returns:
            Dictionary with decrypted fields
        """
        decrypted_data = data.copy()
        
        for key, value in data.items():
            if isinstance(value, str) and value.startswith("ENC:"):
                try:
                    encrypted_part = value[4:]  # Remove "ENC:" prefix
                    decrypted_data[key] = self.decrypt(encrypted_part)
                    logger.debug(f"Decrypted field: {key}")
                except Exception as e:
                    logger.error(f"Failed to decrypt field {key}: {e}")
                    # Keep original value if decryption fails
            elif isinstance(value, dict):
                # Recursively decrypt nested dictionaries
                decrypted_data[key] = self.decrypt_dict(value)
        
        return decrypted_data


# Global encryption instance
credential_encryption = CredentialEncryption()