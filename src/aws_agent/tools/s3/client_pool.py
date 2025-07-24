"""S3 client connection pooling for improved performance."""

import threading
from typing import Dict, Optional
import boto3
from botocore.client import BaseClient
import logging
from ...credentials.manager import AWSCredentialManager

logger = logging.getLogger(__name__)


class S3ClientPool:
    """Singleton S3 client pool for connection reuse."""
    
    _instance = None
    _lock = threading.Lock()
    _clients: Dict[str, BaseClient] = {}
    _credential_manager: Optional[AWSCredentialManager] = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_client(self, profile: str = 'default', region: Optional[str] = None) -> BaseClient:
        """Get or create an S3 client for the given profile and region.
        
        Args:
            profile: AWS profile name
            region: AWS region (optional)
            
        Returns:
            boto3 S3 client
        """
        # Create a unique key for this client
        key = f"{profile}:{region or 'default'}"
        
        # Check if client exists and is still valid
        if key in self._clients:
            try:
                # Test the client is still valid
                self._clients[key].list_buckets(MaxBuckets=1)
                return self._clients[key]
            except Exception:
                # Client is invalid, remove it
                logger.debug(f"Removing invalid client for {key}")
                del self._clients[key]
        
        # Create new client
        with self._lock:
            # Double-check in case another thread created it
            if key not in self._clients:
                try:
                    if self._credential_manager:
                        # Use credential manager if available (handles MFA)
                        logger.info(f"Creating S3 client for profile '{profile}' using credential manager")
                        self._clients[key] = self._credential_manager.create_client('s3', profile)
                        logger.info(f"Successfully created S3 client for {key} using credential manager")
                    else:
                        # Fallback to direct boto3 session
                        logger.warning(f"No credential manager set, falling back to boto3.Session for profile '{profile}'")
                        session = boto3.Session(profile_name=profile)
                        self._clients[key] = session.client('s3', region_name=region)
                        logger.info(f"Created S3 client for {key} using boto3 session")
                except Exception as e:
                    logger.error(f"Failed to create S3 client for {key}: {e}")
                    raise
        
        return self._clients[key]
    
    def clear(self):
        """Clear all cached clients."""
        with self._lock:
            self._clients.clear()
            logger.info("Cleared S3 client pool")
    
    def remove_client(self, profile: str = 'default', region: Optional[str] = None):
        """Remove a specific client from the pool.
        
        Args:
            profile: AWS profile name
            region: AWS region (optional)
        """
        key = f"{profile}:{region or 'default'}"
        with self._lock:
            if key in self._clients:
                del self._clients[key]
                logger.debug(f"Removed S3 client for {key}")
    
    def set_credential_manager(self, credential_manager: AWSCredentialManager):
        """Set the credential manager for the pool.
        
        Args:
            credential_manager: AWS credential manager instance
        """
        self._credential_manager = credential_manager
        # Clear existing clients to force recreation with new manager
        self.clear()


# Global instance
s3_client_pool = S3ClientPool()