#!/usr/bin/env python3

import os
import json
import time
import datetime
import shutil
from typing import List, Dict, Any, Optional

from config.config_manager import config_manager, logger
from core.performance import perf_tracker


class Message:
    """Represents a message in the conversation."""

    def __init__(self, role: str, content: str, timestamp: Optional[float] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp or time.time()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary representation."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary representation."""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {})
        )


class ConversationManager:
    """Manages conversation history between the user and the model."""

    def __init__(self, history_file: str = config_manager.get("history_file")):
        self.history_file = os.path.join(config_manager.get("working_dir"), history_file)
        self.messages: List[Message] = []
        self.max_history = config_manager.get("max_history_entries", 100)
        self.load_history()
        self.last_save_time = time.time()
        self.auto_save_interval = config_manager.get("auto_save_interval", 300)  # 5 minutes
        logger.info(f"Initialized ConversationManager with file: {self.history_file}")

    def load_history(self) -> None:
        """Load conversation history from file."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    self.messages = [Message.from_dict(msg) for msg in data.get("messages", [])]
                logger.info(f"Loaded {len(self.messages)} messages from history")
        except Exception as e:
            logger.error(f"Error loading history: {e}")
            self.messages = []

    def save_history(self) -> None:
        """Save conversation history to file."""
        try:
            data = {
                "version": "2.0.0",
                "timestamp": time.time(),
                "messages": [msg.to_dict() for msg in self.messages]
            }

            # Create a backup before writing
            if os.path.exists(self.history_file) and config_manager.get("backup_files", True):
                backup_dir = os.path.join(os.path.dirname(self.history_file), "backups")
                os.makedirs(backup_dir, exist_ok=True)
                backup_file = os.path.join(
                    backup_dir,
                    f"{os.path.basename(self.history_file)}.{int(time.time())}.bak"
                )
                shutil.copy2(self.history_file, backup_file)

            with open(self.history_file, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=2)

            self.last_save_time = time.time()
            logger.debug("Conversation history saved")
        except Exception as e:
            logger.error(f"Error saving history: {e}")

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a message to the conversation history."""
        self.messages.append(Message(role, content, metadata=metadata or {}))

        # Ensure history doesn't exceed max size
        if len(self.messages) > self.max_history:
            removed = len(self.messages) - self.max_history
            self.messages = self.messages[-self.max_history:]
            logger.info(f"Trimmed {removed} old messages from history")

        # Auto-save if interval has passed
        if time.time() - self.last_save_time > self.auto_save_interval:
            self.save_history()

        perf_tracker.increment_counter("messages_added")

    def get_full_history(self) -> str:
        """Get full conversation history as a formatted string."""
        return "\n\n".join([f"[{msg.role}]\n{msg.content}" for msg in self.messages])

    def get_messages(self) -> List[Message]:
        """Get all messages."""
        return self.messages

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.messages = []
        self.save_history()
        logger.info("Conversation history cleared")

    async def export_to_markdown(self, filepath: str) -> str:
        """Export conversation history to a Markdown file."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("# AI Development Assistant Conversation\n\n")
                f.write(f"Exported: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                for msg in self.messages:
                    role_display = "🧑‍💻 User" if msg.role == "User" else "🤖 Assistant"
                    time_str = datetime.datetime.fromtimestamp(msg.timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"## {role_display} ({time_str})\n\n")
                    f.write(f"{msg.content}\n\n")
                    if msg.metadata:
                        f.write("**Metadata:**\n\n")
                        for key, value in msg.metadata.items():
                            f.write(f"- {key}: {value}\n")
                        f.write("\n")

            logger.info(f"Conversation exported to {filepath}")
            return f"Conversation exported to {filepath}"
        except Exception as e:
            error_msg = f"Error exporting conversation: {e}"
            logger.error(error_msg)
            return error_msg