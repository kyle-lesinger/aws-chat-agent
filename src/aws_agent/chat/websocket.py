"""WebSocket handling for AWS Agent chat."""

from typing import Dict, List, Optional
from fastapi import WebSocket
import json
import logging
import asyncio

from ..core.simple_agent import SimpleAWSAgent
from .terminal import TerminalManager
from ..credentials.providers import MFARequiredException
import uuid


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
    
    def __init__(self, agent: SimpleAWSAgent, websocket: WebSocket, 
                 terminal_manager: Optional[TerminalManager] = None, session_id: str = None):
        self.agent = agent
        self.websocket = websocket
        self.terminal_manager = terminal_manager
        self.session_id = session_id
    
    async def handle_message(self, data: dict):
        """Handle incoming WebSocket message."""
        message_type = data.get("type", "message")
        logger.info(f"WebSocket received message type: {message_type}")
        
        try:
            if message_type == "message":
                await self._handle_chat_message(data)
            elif message_type == "get_profiles":
                await self._handle_get_profiles()
            elif message_type == "set_profile":
                await self._handle_set_profile(data)
            elif message_type == "get_history":
                await self._handle_get_history()
            elif message_type == "terminal_create":
                await self._handle_terminal_create(data)
            elif message_type == "terminal_input":
                await self._handle_terminal_input(data)
            elif message_type == "terminal_resize":
                await self._handle_terminal_resize(data)
            elif message_type == "terminal_close":
                await self._handle_terminal_close(data)
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
                self.agent._update_tools_profile()
            except Exception as e:
                await self._send_error(f"Invalid profile: {e}")
                return
        
        # Send thinking indicator
        await self._send_message("Thinking...", msg_type="thinking")
        
        # Get response from agent
        try:
            logger.info(f"WebSocketHandler: About to call agent.achat with profile={profile}")
            response = await self.agent.achat(content, profile)
            logger.info(f"WebSocketHandler: Got response from agent: {response[:100]}")
            
            # If we had an MFA request before and now succeeded, send complete status
            if hasattr(self, '_had_mfa_request') and self._had_mfa_request:
                await self.websocket.send_json({
                    "type": "mfa_terminal_status",
                    "status": "complete"
                })
                self._had_mfa_request = False
                
            await self._send_message(response)
        except MFARequiredException as e:
            logger.info(f"WebSocketHandler: Caught MFARequiredException! Profile={e.profile}, Device={e.mfa_device}")
            
            # Mark that we had an MFA request
            self._had_mfa_request = True
            
            # Send MFA status update to UI
            await self.websocket.send_json({
                "type": "mfa_terminal_status",
                "status": "required",
                "profile": e.profile,
                "mfa_device": e.mfa_device
            })
            
            # Send clear message to user
            await self._send_message(
                f"⚠️ **MFA Required**\n\n"
                f"Please check your terminal window and enter your 6-digit MFA code.\n\n"
                f"Profile: `{e.profile}`\n"
                f"Device: `{e.mfa_device}`",
                msg_type="warning"
            )
        except Exception as e:
            logger.error(f"WebSocketHandler: Caught general exception: {type(e).__name__}: {e}")
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
            self.agent._update_tools_profile()
            await self._send_message(f"Switched to AWS profile: {profile}", msg_type="info")
        except MFARequiredException as e:
            # Profile exists but requires MFA - just set it
            self.agent.profile = profile
            self.agent._update_tools_profile()
            await self._send_message(f"Switched to AWS profile: {profile} (MFA will be required for operations)", msg_type="info")
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
    
    async def _handle_terminal_create(self, data: dict):
        """Handle terminal creation request."""
        if not self.terminal_manager:
            await self._send_error("Terminal feature is not enabled")
            return
        
        try:
            rows = data.get("rows", 24)
            cols = data.get("cols", 80)
            
            # Create output callback
            async def terminal_output(output: str):
                await self.websocket.send_json({
                    "type": "terminal_output",
                    "session_id": session_id,
                    "data": output
                })
            
            # Create terminal session
            session_id = await self.terminal_manager.create_session(
                self.session_id, terminal_output, rows, cols
            )
            
            logger.info(f"Created terminal session {session_id} with size {rows}x{cols}")
            
            await self.websocket.send_json({
                "type": "terminal_created",
                "session_id": session_id
            })
            
        except Exception as e:
            await self._send_error(f"Failed to create terminal: {e}")
    
    async def _handle_terminal_input(self, data: dict):
        """Handle terminal input."""
        if not self.terminal_manager:
            return
        
        session_id = data.get("session_id")
        input_data = data.get("data", "")
        
        try:
            await self.terminal_manager.write_to_session(session_id, input_data)
        except Exception as e:
            await self._send_error(f"Terminal input error: {e}")
    
    async def _handle_terminal_resize(self, data: dict):
        """Handle terminal resize."""
        if not self.terminal_manager:
            return
        
        session_id = data.get("session_id")
        rows = data.get("rows", 24)
        cols = data.get("cols", 80)
        
        try:
            self.terminal_manager.resize_session(session_id, rows, cols)
        except Exception as e:
            await self._send_error(f"Terminal resize error: {e}")
    
    async def _handle_terminal_close(self, data: dict):
        """Handle terminal close."""
        if not self.terminal_manager:
            return
        
        session_id = data.get("session_id")
        
        try:
            await self.terminal_manager.close_session(session_id)
            await self.websocket.send_json({
                "type": "terminal_closed",
                "session_id": session_id
            })
        except Exception as e:
            await self._send_error(f"Terminal close error: {e}")