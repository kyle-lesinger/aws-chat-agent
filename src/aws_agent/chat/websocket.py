"""WebSocket handling for AWS Agent chat."""

from typing import Dict, List, Optional
from fastapi import WebSocket
import json
import logging
import asyncio

from ..core.simple_agent import SimpleAWSAgent


logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept and store a new connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"Client {session_id} connected")
    
    def disconnect(self, session_id: str):
        """Remove a connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
    
    async def send_message(self, message: str, session_id: str):
        """Send a message to a specific client."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        """Broadcast a message to all connected clients."""
        for session_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {session_id}: {e}")


class WebSocketHandler:
    """Handle WebSocket messages for AWS Agent."""
    
    def __init__(self, agent: SimpleAWSAgent, websocket: WebSocket):
        self.agent = agent
        self.websocket = websocket
    
    async def handle_message(self, data: dict):
        """Handle incoming WebSocket message."""
        message_type = data.get("type", "message")
        
        try:
            if message_type == "message":
                await self._handle_chat_message(data)
            elif message_type == "get_profiles":
                await self._handle_get_profiles()
            elif message_type == "set_profile":
                await self._handle_set_profile(data)
            elif message_type == "get_history":
                await self._handle_get_history()
            else:
                await self._send_error(f"Unknown message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self._send_error(str(e))
    
    async def _handle_chat_message(self, data: dict):
        """Handle a chat message."""
        content = data.get("content", "")
        profile = data.get("profile")
        
        if not content:
            await self._send_error("No message content provided")
            return
        
        # Set profile if specified
        if profile and profile != self.agent.profile:
            try:
                if not self.agent.credential_manager.has_profile(profile):
                    await self._send_error(f"Invalid profile: {profile}")
                    return
                self.agent.profile = profile
            except Exception as e:
                await self._send_error(f"Invalid profile: {e}")
                return
        
        # Send thinking indicator
        await self._send_message("Thinking...", msg_type="thinking")
        
        # Get response from agent
        try:
            response = await self.agent.achat(content, profile)
            await self._send_message(response)
        except Exception as e:
            await self._send_error(f"Agent error: {e}")
    
    async def _handle_get_profiles(self):
        """Get available AWS profiles."""
        try:
            profiles = self.agent.credential_manager.list_profiles()
            await self.websocket.send_json({
                "type": "profiles",
                "profiles": profiles,
                "current": self.agent.profile
            })
        except Exception as e:
            await self._send_error(f"Failed to get profiles: {e}")
    
    async def _handle_set_profile(self, data: dict):
        """Set the AWS profile."""
        profile = data.get("profile")
        if not profile:
            await self._send_error("No profile specified")
            return
        
        try:
            if not self.agent.credential_manager.has_profile(profile):
                await self._send_error(f"Profile '{profile}' not found")
                return
            self.agent.profile = profile
            await self._send_message(f"Switched to AWS profile: {profile}", msg_type="info")
        except Exception as e:
            await self._send_error(str(e))
    
    async def _handle_get_history(self):
        """Get operation history."""
        try:
            # For now, return chat history as a simple list
            history = []
            for msg in self.agent.chat_history:
                if hasattr(msg, 'content'):
                    history.append({
                        "role": "human" if msg.__class__.__name__ == "HumanMessage" else "assistant",
                        "content": msg.content
                    })
            await self.websocket.send_json({
                "type": "history",
                "history": history
            })
        except Exception as e:
            await self._send_error(f"Failed to get history: {e}")
    
    async def _send_message(self, content: str, msg_type: str = "message"):
        """Send a message to the client."""
        await self.websocket.send_json({
            "type": msg_type,
            "content": content
        })
    
    async def _send_error(self, error: str):
        """Send an error message to the client."""
        await self.websocket.send_json({
            "type": "error",
            "content": error
        })