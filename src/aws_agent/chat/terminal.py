"""Terminal session management for AWS Agent chat."""

import os
import sys
import asyncio
import uuid
import logging
import signal
import shlex
import yaml
import select
import errno
import fcntl
import termios
import struct
from typing import Dict, Optional, Callable, Any, List, Set
from datetime import datetime, timedelta
from pathlib import Path
import ptyprocess


logger = logging.getLogger(__name__)


class TerminalSession:
    """Represents a single terminal session."""
    
    def __init__(self, session_id: str, rows: int = 24, cols: int = 80):
        self.session_id = session_id
        self.rows = rows
        self.cols = cols
        self.process: Optional[ptyprocess.PtyProcess] = None
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.output_callback: Optional[Callable[[str], None]] = None
        self._reader_task: Optional[asyncio.Task] = None
        
    async def start(self, shell: str = None, env: dict = None):
        """Start the terminal process."""
        try:
            # Use user's default shell or fallback to /bin/bash
            if not shell:
                shell = os.environ.get('SHELL', '/bin/bash')
            
            # Use provided environment or default
            if env is None:
                env = os.environ.copy()
            
            # Start PTY process
            self.process = ptyprocess.PtyProcess.spawn(
                [shell],
                dimensions=(self.rows, self.cols),
                env=env
            )
            
            # Give the shell a moment to write its initial prompt
            await asyncio.sleep(0.1)
            
            # Do an initial read to capture the prompt using select with timeout
            try:
                # Check if there's data available to read (with 0.5 second timeout)
                ready, _, _ = select.select([self.process.fd], [], [], 0.5)
                if ready:
                    initial_output = self.process.read(1024)
                    if initial_output and self.output_callback:
                        await self.output_callback(initial_output.decode('utf-8', errors='replace'))
            except Exception as e:
                logger.debug(f"Initial read exception (this is normal): {e}")
            
            # Now set non-blocking mode
            flags = fcntl.fcntl(self.process.fd, fcntl.F_GETFL)
            fcntl.fcntl(self.process.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            # Start reading output
            self._reader_task = asyncio.create_task(self._read_output())
            
            logger.info(f"Terminal session {self.session_id} started with shell {shell}")
            
        except Exception as e:
            logger.error(f"Failed to start terminal session: {e}")
            raise
    
    async def _read_output(self):
        """Read output from the terminal process."""
        while self.process and self.process.isalive():
            try:
                # Use select to check if data is available (with small timeout)
                ready, _, _ = select.select([self.process.fd], [], [], 0.1)
                
                if ready:
                    # Try to read from the process (non-blocking)
                    try:
                        output = os.read(self.process.fd, 4096)  # Larger buffer
                        if output and self.output_callback:
                            self.last_activity = datetime.now()
                            await self.output_callback(output.decode('utf-8', errors='replace'))
                    except OSError as e:
                        if e.errno == errno.EAGAIN or e.errno == errno.EWOULDBLOCK:
                            # This shouldn't happen if select said data was ready
                            pass
                        else:
                            raise
                else:
                    # No data available, yield control
                    await asyncio.sleep(0.01)
                        
            except EOFError:
                # Process has ended
                break
            except Exception as e:
                logger.error(f"Error reading terminal output: {e}")
                break
    
    async def write_input(self, data: str):
        """Write input to the terminal."""
        if self.process and self.process.isalive():
            try:
                logger.debug(f"Writing to terminal: {repr(data)}")
                self.process.write(data.encode('utf-8'))
                self.last_activity = datetime.now()
            except Exception as e:
                logger.error(f"Error writing to terminal: {e}")
                raise
        else:
            logger.error("Cannot write to terminal: process not alive")
    
    def resize(self, rows: int, cols: int):
        """Resize the terminal."""
        if self.process and self.process.isalive():
            try:
                self.rows = rows
                self.cols = cols
                self.process.setwinsize(rows, cols)
                logger.debug(f"Terminal {self.session_id} resized to {rows}x{cols}")
            except Exception as e:
                logger.error(f"Error resizing terminal: {e}")
    
    async def close(self):
        """Close the terminal session."""
        if self._reader_task:
            self._reader_task.cancel()
            
        if self.process and self.process.isalive():
            try:
                self.process.terminate()
                await asyncio.sleep(0.1)
                if self.process.isalive():
                    self.process.kill()
            except Exception as e:
                logger.error(f"Error closing terminal: {e}")
        
        logger.info(f"Terminal session {self.session_id} closed")
    
    def is_alive(self) -> bool:
        """Check if the terminal process is still running."""
        return self.process is not None and self.process.isalive()
    
    def is_expired(self, timeout_minutes: int = 30) -> bool:
        """Check if the session has expired due to inactivity."""
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)


class TerminalManager:
    """Manages multiple terminal sessions."""
    
    def __init__(self, max_sessions: int = 10, session_timeout: int = 30, config_path: Optional[str] = None):
        self.sessions: Dict[str, TerminalSession] = {}
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Load configuration
        self.config = self._load_config(config_path)
        self.allowed_commands: Optional[Set[str]] = None
        self.blocked_commands: Set[str] = set()
        self.blocked_env_vars: Set[str] = set()
        
        if self.config:
            # Update settings from config
            terminal_config = self.config.get('terminal', {})
            self.max_sessions = terminal_config.get('max_sessions', max_sessions)
            self.session_timeout = terminal_config.get('session_timeout', session_timeout)
            
            # Load security settings
            security = terminal_config.get('security', {})
            allowed = security.get('allowed_commands', [])
            if allowed:
                self.allowed_commands = set(allowed)
            self.blocked_commands = set(security.get('blocked_commands', []))
            self.blocked_env_vars = set(security.get('blocked_env_vars', []))
    
    def _load_config(self, config_path: Optional[str]) -> Optional[dict]:
        """Load terminal configuration from YAML file."""
        if not config_path:
            # Try to find config in project root
            config_path = Path(__file__).parent.parent.parent.parent / "terminal_config.yml"
        
        try:
            if Path(config_path).exists():
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to load terminal config: {e}")
        
        return None
    
    def _is_command_allowed(self, command: str) -> bool:
        """Check if a command is allowed to execute."""
        # Parse the command to get the base command
        try:
            parts = shlex.split(command)
            if not parts:
                return True
            base_command = parts[0]
        except:
            # If we can't parse it, be safe and block it
            return False
        
        # Check against blocked commands
        for blocked in self.blocked_commands:
            if command.startswith(blocked) or base_command == blocked:
                logger.warning(f"Blocked command attempt: {command}")
                return False
        
        # If we have an allowed list, check against it
        if self.allowed_commands is not None:
            if base_command not in self.allowed_commands:
                logger.warning(f"Command not in allowed list: {command}")
                return False
        
        return True
    
    def _sanitize_environment(self) -> dict:
        """Create a sanitized environment for terminal sessions."""
        env = os.environ.copy()
        
        # Remove blocked environment variables
        for var in self.blocked_env_vars:
            env.pop(var, None)
        
        return env
        
    async def start(self):
        """Start the terminal manager."""
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
        logger.info("Terminal manager started")
    
    async def stop(self):
        """Stop the terminal manager and close all sessions."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            
        # Close all sessions
        for session in list(self.sessions.values()):
            await session.close()
        
        self.sessions.clear()
        logger.info("Terminal manager stopped")
    
    async def create_session(self, user_id: str, output_callback: Callable[[str], None],
                           rows: int = 24, cols: int = 80) -> str:
        """Create a new terminal session."""
        # Check session limit
        user_sessions = [s for s in self.sessions.values() if s.session_id.startswith(user_id)]
        if len(user_sessions) >= self.max_sessions:
            raise ValueError(f"Maximum number of sessions ({self.max_sessions}) reached")
        
        # Create new session
        session_id = f"{user_id}_{uuid.uuid4().hex[:8]}"
        session = TerminalSession(session_id, rows, cols)
        session.output_callback = output_callback
        
        # Start the session with sanitized environment
        env = self._sanitize_environment()
        await session.start(env=env)
        
        self.sessions[session_id] = session
        logger.info(f"Created terminal session {session_id}")
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[TerminalSession]:
        """Get a terminal session by ID."""
        return self.sessions.get(session_id)
    
    async def write_to_session(self, session_id: str, data: str):
        """Write input to a terminal session."""
        session = self.get_session(session_id)
        if session:
            await session.write_input(data)
        else:
            raise ValueError(f"Terminal session {session_id} not found")
    
    def resize_session(self, session_id: str, rows: int, cols: int):
        """Resize a terminal session."""
        session = self.get_session(session_id)
        if session:
            session.resize(rows, cols)
        else:
            raise ValueError(f"Terminal session {session_id} not found")
    
    async def close_session(self, session_id: str):
        """Close a terminal session."""
        session = self.sessions.pop(session_id, None)
        if session:
            await session.close()
        else:
            raise ValueError(f"Terminal session {session_id} not found")
    
    async def _cleanup_expired_sessions(self):
        """Periodically clean up expired sessions."""
        while True:
            try:
                # Check for expired sessions
                expired = []
                for session_id, session in self.sessions.items():
                    if not session.is_alive() or session.is_expired(self.session_timeout):
                        expired.append(session_id)
                
                # Close expired sessions
                for session_id in expired:
                    logger.info(f"Cleaning up expired session {session_id}")
                    await self.close_session(session_id)
                
                # Wait before next cleanup
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)