"""MFA provider wrapper that notifies web UI when MFA is needed."""

import asyncio
import getpass
import logging
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class NotifyingMFACallback:
    """MFA callback that notifies web UI while using terminal prompt."""
    
    def __init__(self, notifier=None):
        self.notifier = notifier
        self.executor = ThreadPoolExecutor(max_workers=1)
        
    def __call__(self, profile: str, mfa_device: str) -> str:
        """Prompt for MFA code with web notification."""
        logger.info(f"NotifyingMFACallback called for {profile}")
        
        # Try to notify web UI (non-blocking)
        if self.notifier:
            try:
                # Run notification in background
                future = self.executor.submit(self._notify_async, profile, mfa_device)
                # Don't wait for it to complete
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
        
        # Use terminal prompt immediately
        logger.info("Using terminal prompt for MFA")
        mfa_code = getpass.getpass("🔢 Enter your MFA code: ")
        
        # Notify completion
        if self.notifier:
            try:
                future = self.executor.submit(self._notify_complete_async, profile)
            except Exception as e:
                logger.error(f"Failed to send completion notification: {e}")
                
        return mfa_code
    
    def _notify_async(self, profile: str, mfa_device: str):
        """Run async notification in thread."""
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self.notifier.notify_mfa_needed(profile, mfa_device)
            )
            loop.close()
        except Exception as e:
            logger.error(f"Notification error: {e}")
            
    def _notify_complete_async(self, profile: str):
        """Run async completion notification in thread."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self.notifier.notify_mfa_complete(profile)
            )
            loop.close()
        except Exception as e:
            logger.error(f"Completion notification error: {e}")