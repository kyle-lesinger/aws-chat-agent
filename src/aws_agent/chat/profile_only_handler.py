"""Lightweight handler for profile operations without full agent."""

import logging
from typing import Optional
from fastapi import WebSocket
from ..credentials.manager import AWSCredentialManager

logger = logging.getLogger(__name__)


class ProfileOnlyHandler:
    """Handle profile operations without requiring full agent initialization."""
    
    def __init__(self, websocket: WebSocket, credential_manager: Optional[AWSCredentialManager] = None):
        self.websocket = websocket
        self.credential_manager = credential_manager or AWSCredentialManager()
        
    async def handle_get_profiles(self):
        """Get available AWS profiles."""
        try:
            profiles = self.credential_manager.list_profiles()
            await self.websocket.send_json({
                "type": "profiles",
                "profiles": profiles,
                "current": "default"
            })
        except Exception as e:
            logger.error(f"Failed to get profiles: {e}")
            await self.websocket.send_json({
                "type": "error",
                "content": f"Failed to get profiles: {e}"
            })
            
    async def handle_profile_selected(self, data: dict):
        """Handle profile selection for preemptive MFA."""
        profile = data.get("profile")
        if not profile:
            return
            
        # Just acknowledge for now
        await self.websocket.send_json({
            "type": "profile_selected_ack",
            "profile": profile
        })