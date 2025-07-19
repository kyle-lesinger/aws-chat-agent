"""S3 client connection pooling for improved performance."""

import threading
from typing import Dict, Optional
import boto3
from botocore.client import BaseClient
import logging

logger = logging.getLogger(__name__)


class S3ClientPool:
    """Singleton S3 client pool for connection reuse."""
    
    _instance = None
    _lock = threading.Lock()
    _clients: Dict[str, BaseClient] = {}
    
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
                    session = boto3.Session(profile_name=profile)
                    self._clients[key] = session.client('s3', region_name=region)
                    logger.debug(f"Created new S3 client for {key}")
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


# Global instance
s3_client_pool = S3ClientPool()