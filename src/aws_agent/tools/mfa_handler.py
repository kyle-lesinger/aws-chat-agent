"""MFA handler for tools that need authentication."""

import asyncio
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MFARequest:
    """MFA request information."""
    profile: str
    mfa_device: str
    request_id: str
    callback: Optional[Callable[[str], None]] = None


class MFAHandler:
    """Singleton handler for MFA requests."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._pending_request: Optional[MFARequest] = None
        self._mfa_callback: Optional[Callable] = None
        self._event = asyncio.Event()
        self._mfa_code: Optional[str] = None
    
    def set_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set the callback for MFA requests."""
        self._mfa_callback = callback
        logger.info("MFA callback set")
    
    def request_mfa(self, profile: str, mfa_device: str) -> Optional[str]:
        """Request MFA code from user."""
        if not self._mfa_callback:
            logger.error("No MFA callback set")
            return None
        
        # Send MFA request
        import uuid
        request_id = str(uuid.uuid4())
        
        logger.info(f"Requesting MFA for profile {profile}, device {mfa_device}")
        
        # Call the callback with MFA request
        self._mfa_callback({
            "type": "mfa_required",
            "profile": profile,
            "mfa_device": mfa_device,
            "request_id": request_id
        })
        
        # In a real implementation, this would wait for the response
        # For now, return None to indicate MFA is pending
        return None
    
    def provide_mfa_code(self, request_id: str, mfa_code: str):
        """Provide MFA code for a pending request."""
        logger.info(f"MFA code provided for request {request_id}")
        self._mfa_code = mfa_code
        if hasattr(self, '_event'):
            self._event.set()


# Global MFA handler instance
mfa_handler = MFAHandler()