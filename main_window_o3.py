#!/usr/bin/env python3
import sys
import asyncio
import qasync

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QLineEdit, QPushButton, QLabel, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QTextDocument

# Import your assistant modules
from config.config_manager import config_manager
from core.dev_assistant import DevAssistant
from cli.command_handler import CommandHandler

class ChatBubble(QFrame):
    """
    A single chat bubble for displaying either a user or assistant message.
    Automatically adjusts height based on text length.
    """
    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.is_user = is_user

        # Styling for the bubble background
        self.setStyleSheet(self._bubble_style())
        self.setFrameShape(QFrame.Shape.NoFrame)

        # Layout for the bubble
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # The label that displays the text
        self.label = QLabel(text, self)
        self.label.setWordWrap(True)

        # Set a maximum width so that text will wrap instead of expanding horizontally
        # Adjust this value for your preferred bubble width
        self.label.setMaximumWidth(500)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout.addWidget(self.label)

        # Align user messages to the right; assistant messages to the left
        if self.is_user:
            layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        else:
            layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

    def _bubble_style(self) -> str:
        """
        Return the stylesheet for user vs. assistant messages.
        """
        if self.is_user:
            return """
                background-color: #DCF8C6;
                border-radius: 10px;
                padding: 5px;
                color: #000000;
            """
        else:
            return """
                background-color: #F1F0F0;
                border-radius: 10px;
                padding: 5px;
                color: #000000;
            """

    def sizeHint(self) -> QSize:
        """
        Recompute how large this bubble should be, based on the label’s text length.
        """
        doc = QTextDocument()
        doc.setPlainText(self.label.text())
        # Match the label’s wrapping width
        doc.setTextWidth(self.label.maximumWidth())

        # The doc size gives us the needed space for the text
        text_size = doc.size()

        # Add margins around the text
        width = text_size.width() + 30
        height = text_size.height() + 20

        return QSize(int(width), int(height))

    def update_text(self, new_text: str):
        """
        Update the bubble’s text (useful for streaming partial chunks).
        """
        self.label.setText(new_text)
        # Force a size recalculation so the bubble can grow/shrink
        self.updateGeometry()
        if self.parentWidget():
            self.parentWidget().adjustSize()


class ChatWindow(QMainWindow):
    """
    Main window with a scrollable chat area (chat bubbles) and an input field.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Development Assistant - Chat")
        self.resize(800, 600)

        # References for streaming
        self._assistant_bubble = None

        # References to the AI modules
        self.dev_assistant = None
        self.command_handler = None

        # Build the UI
        self._init_ui()

    def _init_ui(self):
        # Main container
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Scroll area to hold chat bubbles
        self.chat_area = QScrollArea(self)
        self.chat_area.setWidgetResizable(True)

        # Content widget and layout inside the scroll area
        self.chat_content = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_content)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_area.setWidget(self.chat_content)

        main_layout.addWidget(self.chat_area)

        # Input area (line + send button)
        input_layout = QHBoxLayout()
        self.input_line = QLineEdit(self)
        self.input_line.setPlaceholderText("Type your message here...")
        self.input_line.returnPressed.connect(self._on_user_input)
        input_layout.addWidget(self.input_line)

        send_button = QPushButton("Send", self)
        send_button.clicked.connect(self._on_user_input)
        input_layout.addWidget(send_button)

        main_layout.addLayout(input_layout)

    def add_message(self, text: str, is_user: bool) -> ChatBubble:
        """
        Create a new ChatBubble, add it to the layout, and scroll to bottom.
        """
        bubble = ChatBubble(text, is_user, self.chat_content)
        self.chat_layout.addWidget(bubble)
        self._scroll_to_bottom()
        return bubble

    def _scroll_to_bottom(self):
        """Scroll the chat area to the bottom."""
        scrollbar = self.chat_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_user_input(self):
        """
        Called when the user presses Enter or clicks 'Send'.
        """
        user_text = self.input_line.text().strip()
        if not user_text:
            return

        # Show the user's message
        self.add_message(f">>> {user_text}", is_user=True)
        self.input_line.clear()

        # Process input asynchronously
        asyncio.create_task(self._process_input(user_text))

    async def _process_input(self, user_text: str):
        """
        Determine if the text is a command or normal conversation, then handle it.
        """
        if user_text.startswith(":"):
            await self._execute_command(user_text)
        else:
            await self._chat_with_assistant(user_text)

    async def _execute_command(self, command_text: str):
        """Execute a command via the CommandHandler."""
        if not self.command_handler:
            self.add_message("Command handler not initialized.", is_user=False)
            return

        try:
            command_args = [command_text]
            result = await self.command_handler.handle_command(command_args)
            if result:
                self.add_message(result, is_user=False)
        except Exception as e:
            self.add_message(f"Error processing command: {e}", is_user=False)

    async def _chat_with_assistant(self, user_text: str):
        """
        Add user message to conversation, display a 'thinking' bubble,
        then stream the assistant's response.
        """
        if not self.dev_assistant:
            self.add_message("DevAssistant not initialized.", is_user=False)
            return

        # Add user message to conversation
        self.dev_assistant.conversation.add_message("User", user_text)

        # Placeholder bubble for streaming
        bubble = self.add_message("AI Assistant is thinking...", is_user=False)
        self._assistant_bubble = bubble

        response_chunks = []

        async def handle_chunk(chunk: str):
            response_chunks.append(chunk)
            current_text = self._assistant_bubble.label.text()
            # Remove placeholder text on first chunk
            if current_text == "AI Assistant is thinking...":
                current_text = ""
            new_text = current_text + chunk
            self._assistant_bubble.update_text(new_text)
            self._scroll_to_bottom()

        try:
            await self.dev_assistant.model_api.stream_response(
                self.dev_assistant.model,
                self.dev_assistant.conversation.get_full_history(),
                handle_chunk
            )
        except Exception as e:
            self.add_message(f"Error streaming response: {e}", is_user=False)
            return

        # Finalize conversation text
        full_response = "".join(response_chunks)
        self.dev_assistant.conversation.add_message("Model", full_response)
        self._assistant_bubble = None

    async def initialize_app(self):
        """
        Set up DevAssistant and CommandHandler, then scan for projects.
        """
        try:
            model = config_manager.get("default_model")
            self.dev_assistant = DevAssistant(model)
            self.command_handler = CommandHandler(self.dev_assistant)

            await self.dev_assistant.project_manager.scan_projects()
            self.add_message("Application initialized.", is_user=False)

        except Exception as e:
            self.add_message(f"Error during initialization: {e}", is_user=False)


def main():
    app = QApplication(sys.argv)

    # Integrate asyncio event loop with PyQt
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = ChatWindow()
    window.show()

    with loop:
        asyncio.ensure_future(window.initialize_app())
        loop.run_forever()


if __name__ == "__main__":
    main()
