"""Simple authentication for AWS Agent chat."""

import os
import secrets
import hashlib
from typing import Optional, Dict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SimpleAuthManager:
    """Simple API key based authentication manager.
    
    This is a basic implementation. For production use, consider:
    - JWT tokens with expiration
    - OAuth2 integration
    - Database-backed user management
    """
    
    def __init__(self):
        self.api_keys: Dict[str, Dict] = {}
        self._load_api_keys()
    
    def _load_api_keys(self):
        """Load API keys from environment or generate default."""
        # Check for API key in environment
        env_key = os.environ.get('AWS_AGENT_API_KEY')
        if env_key:
            self.api_keys[self._hash_key(env_key)] = {
                'name': 'env_key',
                'created': datetime.now(),
                'last_used': None
            }
            logger.info("Loaded API key from environment")
        else:
            # Generate a default key for demo purposes
            default_key = secrets.token_urlsafe(32)
            self.api_keys[self._hash_key(default_key)] = {
                'name': 'default',
                'created': datetime.now(),
                'last_used': None
            }
            logger.warning(
                f"No AWS_AGENT_API_KEY found in environment. "
                f"Generated temporary key: {default_key}"
            )
            logger.warning(
                "For production use, set AWS_AGENT_API_KEY environment variable"
            )
    
    def _hash_key(self, key: str) -> str:
        """Hash API key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def validate_api_key(self, api_key: Optional[str]) -> bool:
        """Validate an API key.
        
        Args:
            api_key: The API key to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not api_key:
            return False
        
        hashed = self._hash_key(api_key)
        if hashed in self.api_keys:
            # Update last used timestamp
            self.api_keys[hashed]['last_used'] = datetime.now()
            return True
        
        return False
    
    def generate_api_key(self, name: str) -> str:
        """Generate a new API key.
        
        Args:
            name: Name/description for the key
            
        Returns:
            The generated API key
        """
        key = secrets.token_urlsafe(32)
        self.api_keys[self._hash_key(key)] = {
            'name': name,
            'created': datetime.now(),
            'last_used': None
        }
        logger.info(f"Generated new API key for '{name}'")
        return key
    
    def revoke_api_key(self, api_key: str) -> bool:
        """Revoke an API key.
        
        Args:
            api_key: The API key to revoke
            
        Returns:
            True if revoked, False if not found
        """
        hashed = self._hash_key(api_key)
        if hashed in self.api_keys:
            del self.api_keys[hashed]
            logger.info("Revoked API key")
            return True
        return False


# Global auth manager instance
auth_manager = SimpleAuthManager()