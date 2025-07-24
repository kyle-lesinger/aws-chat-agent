"""Mock agent for when OpenAI is not available."""

import logging
from typing import List, Optional, Dict, Any
from ..credentials.manager import AWSCredentialManager

logger = logging.getLogger(__name__)


class MockAWSAgent:
    """Mock AWS Agent that provides basic functionality without LLM."""
    
    def __init__(self, credential_manager: Optional[AWSCredentialManager] = None):
        self.credential_manager = credential_manager or AWSCredentialManager()
        self.profile = "default"
        self.chat_history = []
        
    async def achat(self, message: str, profile: Optional[str] = None) -> str:
        """Mock chat that returns helpful message."""
        return (
            "🤖 Mock Agent Active\n\n"
            "The OpenAI API key is not configured, so I'm running in limited mode.\n"
            "Available operations:\n"
            "- List AWS profiles\n"
            "- Switch profiles\n"
            "- View profile information\n\n"
            "To enable full functionality, please set your OPENAI_API_KEY in the .env file."
        )
        
    def _update_tools_profile(self):
        """Update tools with current profile."""
        # Mock implementation
        pass
        
    def list_profiles(self) -> List[str]:
        """List available profiles."""
        return self.credential_manager.list_profiles()