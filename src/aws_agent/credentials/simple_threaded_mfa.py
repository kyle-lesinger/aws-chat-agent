"""Simple MFA callback that prompts in terminal."""

import logging
import sys
from typing import Optional, TYPE_CHECKING
import asyncio
import json
import time
from pathlib import Path

if TYPE_CHECKING:
    from ..chat.websocket import ConnectionManager

logger = logging.getLogger(__name__)


class SimpleMFACallback:
    """Simple MFA callback that prompts in terminal."""
    
    _connection_manager: Optional['ConnectionManager'] = None
    
    def __init__(self, timeout: int = 60):
        self.timeout = timeout
    
    @classmethod
    def set_connection_manager(cls, connection_manager: 'ConnectionManager'):
        """Set the global connection manager for WebSocket notifications."""
        cls._connection_manager = connection_manager
        
    def __call__(self, profile: str, mfa_device: str) -> str:
        """Get MFA code from terminal."""
        logger.info(f"[MFA] Requesting MFA for profile {profile}")
        
        # Write MFA notification to a shared file that the server can monitor
        notification_dir = Path.home() / ".aws_agent" / "notifications"
        notification_dir.mkdir(parents=True, exist_ok=True)
        
        notification_file = notification_dir / "mfa_status.json"
        notification = {
            "type": "mfa_required",
            "profile": profile,
            "mfa_device": mfa_device,
            "timestamp": time.time()
        }
        
        try:
            with open(notification_file, 'w') as f:
                json.dump(notification, f)
            logger.info(f"[MFA] Wrote MFA notification to {notification_file}")
        except Exception as e:
            logger.error(f"[MFA] Failed to write notification file: {e}")
        
        # Also try WebSocket notification if connection manager is available
        if self._connection_manager:
            try:
                # Create notification task
                async def send_notification():
                    # Notify all connected clients
                    message = {
                        "type": "mfa_terminal_status",
                        "status": "required",
                        "profile": profile,
                        "mfa_device": mfa_device
                    }
                    
                    for session_id, websocket in self._connection_manager.active_connections.items():
                        try:
                            await websocket.send_json(message)
                            logger.info(f"[MFA] Sent MFA notification to WebSocket session {session_id}")
                        except Exception as e:
                            logger.error(f"[MFA] Failed to send notification to session {session_id}: {e}")
                
                # Check if there's an event loop running
                try:
                    loop = asyncio.get_running_loop()
                    # Schedule the coroutine to run in the existing loop
                    asyncio.create_task(send_notification())
                except RuntimeError:
                    # No event loop running, create a new one
                    asyncio.run(send_notification())
                    
            except Exception as e:
                logger.error(f"[MFA] Failed to send WebSocket notification: {e}")
        
        # Show terminal prompt
        if sys.stdout.isatty():
            print(f"\n{'='*60}")
            print(f"🔐 MFA Required for AWS Profile: {profile}")
            print(f"📱 Device: {mfa_device}")
            print(f"{'='*60}\n")
            
        # Simple terminal input
        try:
            if sys.stdin.isatty():
                code = input("🔢 Enter your 6-digit MFA code: ")
                logger.info(f"[MFA] Code entered for profile {profile}")
                
                # Write completion notification
                try:
                    notification = {
                        "type": "mfa_complete",
                        "profile": profile,
                        "timestamp": time.time()
                    }
                    with open(notification_file, 'w') as f:
                        json.dump(notification, f)
                    logger.info(f"[MFA] Wrote completion notification")
                except Exception as e:
                    logger.error(f"[MFA] Failed to write completion notification: {e}")
                
                # Send completion notification via WebSocket
                if self._connection_manager:
                    try:
                        async def send_complete():
                            message = {
                                "type": "mfa_terminal_status",
                                "status": "complete"
                            }
                            for session_id, websocket in self._connection_manager.active_connections.items():
                                try:
                                    await websocket.send_json(message)
                                except Exception as e:
                                    logger.error(f"[MFA] Failed to send complete notification: {e}")
                        
                        try:
                            loop = asyncio.get_running_loop()
                            asyncio.create_task(send_complete())
                        except RuntimeError:
                            asyncio.run(send_complete())
                    except Exception as e:
                        logger.error(f"[MFA] Failed to send complete notification: {e}")
                
                return code.strip()
            else:
                raise RuntimeError("No terminal available for MFA input")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"MFA input error: {e}")
            raise
