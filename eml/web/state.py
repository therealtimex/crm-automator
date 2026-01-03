"""
State Management Module for CRM Automator Web UI

This module provides global state management and custom logging handlers
for the web UI. It tracks file processing state, progress, and captures
application logs for real-time display.

Classes:
    ProcessingState: Manages upload queue and processing status
    WebUILogHandler: Custom logging handler for UI log display

Exports:
    state: Global singleton instance of ProcessingState
"""

import logging
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class ProcessingState:
    """Global state for processing operations (single-user localhost app)"""
    def __init__(self):
        self.is_processing = False
        self.current_file = ""
        self.progress = 0
        self.total = 0
        self.logs = []
        self.uploaded_files: List[Path] = []
        self.stats = {
            "total": 0,
            "processed": 0,
            "suppressed": 0,
            "failed": 0
        }

    def get_total_size(self) -> int:
        """Calculate total size of all uploaded files in bytes"""
        total = 0
        for file_path in self.uploaded_files:
            try:
                if file_path.exists():
                    total += file_path.stat().st_size
            except Exception as e:
                logger.warning(f"Failed to get size for {file_path}: {e}")
        return total

    def format_size(self, size_bytes: int) -> str:
        """Format bytes into human-readable size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def cleanup_files(self):
        """Clean up uploaded temporary files"""
        for file_path in self.uploaded_files:
            try:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Cleaned up temporary file: {file_path}")
            except Exception as e:
                logger.error(f"Failed to cleanup file {file_path}: {e}")
        self.uploaded_files.clear()

# Global state (acceptable for localhost-only app)
state = ProcessingState()

class WebUILogHandler(logging.Handler):
    """Custom logging handler that captures logs and adds them to state.logs"""
    def __init__(self, state_obj):
        super().__init__()
        self.state = state_obj
        # Set formatter to match the desired format
        self.setFormatter(logging.Formatter('%(levelname)s - %(name)s - %(message)s'))

    def emit(self, record):
        try:
            # Format the log message
            log_msg = self.format(record)
            timestamp = datetime.now().strftime('%H:%M:%S')

            # Add emoji based on log level
            level_emoji = {
                'DEBUG': '🔍',
                'INFO': 'ℹ️',
                'WARNING': '⚠️',
                'ERROR': '❌',
                'CRITICAL': '🚨'
            }
            emoji = level_emoji.get(record.levelname, '•')

            # Append to state logs
            formatted_log = f"[{timestamp}] {emoji} {log_msg}"
            self.state.logs.append(formatted_log)

            # Keep only last 200 logs to prevent memory issues
            if len(self.state.logs) > 200:
                self.state.logs = self.state.logs[-200:]
        except Exception:
            # Don't let logging errors break the handler
            pass
