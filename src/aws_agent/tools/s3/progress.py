"""Progress tracking utilities for S3 operations."""

import sys
import threading
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)


class ProgressPercentage:
    """Progress callback for S3 transfers."""
    
    def __init__(self, filename: str, size: int, callback: Optional[Callable[[int, int], None]] = None):
        """Initialize progress tracker.
        
        Args:
            filename: Name of the file being transferred
            size: Total size in bytes
            callback: Optional callback function that receives (bytes_transferred, total_bytes)
        """
        self._filename = filename
        self._size = size
        self._seen_so_far = 0
        self._lock = threading.Lock()
        self._callback = callback
        self._last_percentage = -1
    
    def __call__(self, bytes_amount: int):
        """Called by boto3 during transfer with bytes transferred.
        
        Args:
            bytes_amount: Number of bytes transferred in this call
        """
        with self._lock:
            self._seen_so_far += bytes_amount
            
            if self._size > 0:
                percentage = (self._seen_so_far / self._size) * 100
                
                # Only log/print if percentage changed by at least 1%
                if int(percentage) > self._last_percentage:
                    self._last_percentage = int(percentage)
                    
                    # Call custom callback if provided
                    if self._callback:
                        self._callback(self._seen_so_far, self._size)
                    
                    # Log progress
                    logger.debug(
                        f"{self._filename}: {self._seen_so_far:,} / {self._size:,} bytes "
                        f"({percentage:.1f}%)"
                    )
            else:
                # Size unknown
                logger.debug(f"{self._filename}: {self._seen_so_far:,} bytes transferred")


class ConsoleProgressBar:
    """Console progress bar for S3 transfers."""
    
    def __init__(self, filename: str, size: int):
        """Initialize console progress bar.
        
        Args:
            filename: Name of the file being transferred
            size: Total size in bytes
        """
        self.filename = filename
        self.size = size
        self.progress = ProgressPercentage(filename, size, self._update_bar)
        self._last_printed_len = 0
    
    def _update_bar(self, bytes_transferred: int, total_bytes: int):
        """Update console progress bar."""
        if total_bytes <= 0:
            return
        
        percentage = (bytes_transferred / total_bytes) * 100
        bar_length = 40
        filled_length = int(bar_length * bytes_transferred // total_bytes)
        
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        
        # Format sizes
        transferred_mb = bytes_transferred / (1024 * 1024)
        total_mb = total_bytes / (1024 * 1024)
        
        # Create progress string
        progress_str = f"\r{self.filename}: |{bar}| {percentage:.1f}% ({transferred_mb:.1f}/{total_mb:.1f} MB)"
        
        # Clear previous line if it was longer
        if len(progress_str) < self._last_printed_len:
            sys.stdout.write('\r' + ' ' * self._last_printed_len + '\r')
        
        sys.stdout.write(progress_str)
        sys.stdout.flush()
        
        self._last_printed_len = len(progress_str)
        
        # Print newline when complete
        if bytes_transferred >= total_bytes:
            print()  # New line after completion


def format_bytes(size: int) -> str:
    """Format bytes into human-readable string.
    
    Args:
        size: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"