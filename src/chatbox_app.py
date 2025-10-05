import asyncio
import json
import tkinter as tk
from tkinter import ttk, scrolledtext
from datetime import datetime
from typing import Optional, Dict
import uuid
import threading
from src.lora_modem import LoRaHostClient


class ChatMessage:
    """Chat message with metadata."""

    def __init__(self, msg_id: str, username: str, content: str, timestamp: float, is_own: bool = False):
        self.msg_id = msg_id
        self.username = username
        self.content = content
        self.timestamp = timestamp
        self.is_own = is_own
        self.acknowledged = False


class MessageProtocol:
    """Handles message serialization/deserialization and ACK management."""

    MSG_TYPE_CHAT = "chat"
    MSG_TYPE_ACK = "ack"

    @staticmethod
    def create_chat_message(username: str, content: str) -> tuple[str, str]:
        """Create a chat message and return (msg_id, serialized_json)."""
        msg_id = str(uuid.uuid4())[:8]  # Short ID for LoRa efficiency
        message = {
            "type": MessageProtocol.MSG_TYPE_CHAT,
            "id": msg_id,
            "username": username,
            "content": content,
            "timestamp": datetime.now().timestamp()
        }
        return msg_id, json.dumps(message)

    @staticmethod
    def create_ack_message(msg_id: str, username: str) -> str:
        """Create an ACK message."""
        ack = {
            "type": MessageProtocol.MSG_TYPE_ACK,
            "ack_id": msg_id,
            "username": username,
            "timestamp": datetime.now().timestamp()
        }
        return json.dumps(ack)

    @staticmethod
    def parse_message(raw_payload: str) -> Optional[Dict]:
        """Parse incoming message, returns dict or None if invalid."""
        try:
            data = json.loads(raw_payload)
            if not isinstance(data, dict) or "type" not in data:
                return None
            return data
        except (json.JSONDecodeError, ValueError):
            return None


class ModernChatApp:
    def __init__(self, username: str, port: Optional[str] = None):
        self.username = username
        self.port = port

        # LoRa client
        self.lora_client: Optional[LoRaHostClient] = None

        # Message tracking
        self.messages: Dict[str, ChatMessage] = {}
        self.pending_acks: set = set()

        # Threading coordination
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.asyncio_thread: Optional[threading.Thread] = None
        self.running = False

        # UI components
        self.root: Optional[tk.Tk] = None
        self.chat_display: Optional[scrolledtext.ScrolledText] = None
        self.message_entry: Optional[tk.Entry] = None
        self.send_button: Optional[ttk.Button] = None
        self.status_label: Optional[tk.Label] = None

        # Colors for modern UI
        self.colors = {
            "bg": "#1e1e1e",
            "fg": "#ffffff",
            "chat_bg": "#2d2d2d",
            "input_bg": "#3c3c3c",
            "own_msg": "#0078d4",
            "other_msg": "#3a3a3a",
            "ack": "#00ff00",
            "pending": "#ffaa00",
            "system": "#888888"
        }

    def run(self):
        """Start the application."""
        # Start asyncio in the background thread
        self.running = True
        self.asyncio_thread = threading.Thread(target=self._run_asyncio_loop, daemon=True)
        self.asyncio_thread.start()

        # Wait for loop to be ready
        while self.loop is None:
            threading.Event().wait(0.01)

        # Build and run UI
        self._build_ui()

        # Schedule LoRa client initialization
        asyncio.run_coroutine_threadsafe(self._init_lora(), self.loop)

        # Start TKinter main loop
        self.root.mainloop()

        # Cleanup on exit
        self.running = False
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._cleanup(), self.loop)

    def _run_asyncio_loop(self):
        """Run asyncio event loop in the background thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _init_lora(self):
        """Initialize LoRa client."""
        try:
            self.lora_client = LoRaHostClient(port=self.port)
            await self.lora_client.open()
            self._update_status("Connected to LoRa", "success")

            # Start message consumer
            asyncio.create_task(self._consume_messages())

        except Exception as e:
            self._update_status(f"LoRa Error: {e}", "error")

    async def _cleanup(self):
        """Cleanup resources."""
        if self.lora_client:
            try:
                await self.lora_client.close()
            except Exception:
                pass

        if self.loop:
            self.loop.stop()

    async def _consume_messages(self):
        """Consume incoming LoRa messages."""
        if not self.lora_client:
            return

        try:
            async for raw_payload in self.lora_client.messages():
                await self._handle_incoming_message(raw_payload)
        except Exception as e:
            self._update_status(f"RX Error: {e}", "error")

    async def _handle_incoming_message(self, raw_payload: str):
        """Process an incoming message or ACK."""
        data = MessageProtocol.parse_message(raw_payload)
        if not data:
            return

        msg_type = data.get("type")

        if msg_type == MessageProtocol.MSG_TYPE_CHAT:
            # Received a chat message
            msg_id = data.get("id")
            username = data.get("username", "Unknown")
            content = data.get("content", "")
            timestamp = data.get("timestamp", datetime.now().timestamp())

            # Don't display our own messages from echo
            if username == self.username:
                return

            # Create and display message
            msg = ChatMessage(msg_id, username, content, timestamp, is_own=False)
            self.messages[msg_id] = msg
            self._display_message(msg)

            # Send ACK back
            ack_payload = MessageProtocol.create_ack_message(msg_id, self.username)
            try:
                await self.lora_client.send_text(ack_payload)
            except Exception:
                pass

        elif msg_type == MessageProtocol.MSG_TYPE_ACK:
            # Received an ACK for our message
            ack_id = data.get("ack_id")
            ack_username = data.get("username", "Unknown")

            if ack_id in self.messages:
                msg = self.messages[ack_id]
                if not msg.acknowledged:
                    msg.acknowledged = True
                    self._update_message_status(msg, ack_username)

            if ack_id in self.pending_acks:
                self.pending_acks.remove(ack_id)

    def _build_ui(self):
        """Build the TKinter UI."""
        self.root = tk.Tk()
        self.root.title(f"Off-grid Chat - {self.username}")
        self.root.geometry("600x700")
        self.root.configure(bg=self.colors["bg"])

        # Style configuration
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TButton",
                        background=self.colors["own_msg"],
                        foreground=self.colors["fg"],
                        borderwidth=0,
                        focuscolor='none',
                        padding=10,
                        font=('Segoe UI', 10))
        style.map("TButton",
                  background=[('active', '#005a9e')])

        # Header
        header_frame = tk.Frame(self.root, bg=self.colors["own_msg"], height=60)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)

        title_label = tk.Label(header_frame,
                               text="Off-grid Chat",
                               bg=self.colors["own_msg"],
                               fg=self.colors["fg"],
                               font=('Segoe UI', 16, 'bold'))
        title_label.pack(side=tk.LEFT, padx=20, pady=15)

        user_label = tk.Label(header_frame,
                              text=f"@{self.username}",
                              bg=self.colors["own_msg"],
                              fg=self.colors["fg"],
                              font=('Segoe UI', 12))
        user_label.pack(side=tk.RIGHT, padx=20, pady=15)

        # Status bar
        status_frame = tk.Frame(self.root, bg=self.colors["input_bg"], height=30)
        status_frame.pack(fill=tk.X, side=tk.TOP)
        status_frame.pack_propagate(False)

        self.status_label = tk.Label(status_frame,
                                     text="Initializing...",
                                     bg=self.colors["input_bg"],
                                     fg=self.colors["system"],
                                     font=('Segoe UI', 9),
                                     anchor=tk.W)
        self.status_label.pack(fill=tk.X, padx=10, pady=5)

        # Chat display area
        chat_frame = tk.Frame(self.root, bg=self.colors["bg"])
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.chat_display = scrolledtext.ScrolledText(chat_frame,
                                                      bg=self.colors["chat_bg"],
                                                      fg=self.colors["fg"],
                                                      font=('Segoe UI', 10),
                                                      wrap=tk.WORD,
                                                      borderwidth=0,
                                                      highlightthickness=0,
                                                      padx=10,
                                                      pady=10,
                                                      state=tk.DISABLED)
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        # Configure text tags for styling
        self.chat_display.tag_config("own",
                                     background=self.colors["own_msg"],
                                     foreground=self.colors["fg"],
                                     spacing1=5,
                                     spacing3=5,
                                     lmargin1=100,
                                     rmargin=10,
                                     wrap=tk.WORD)
        self.chat_display.tag_config("other",
                                     background=self.colors["other_msg"],
                                     foreground=self.colors["fg"],
                                     spacing1=5,
                                     spacing3=5,
                                     lmargin1=10,
                                     lmargin2=10,
                                     rmargin=100,
                                     wrap=tk.WORD)
        self.chat_display.tag_config("username",
                                     foreground="#aaaaaa",
                                     font=('Segoe UI', 9, 'bold'))
        self.chat_display.tag_config("timestamp",
                                     foreground=self.colors["system"],
                                     font=('Segoe UI', 8))
        self.chat_display.tag_config("status",
                                     foreground=self.colors["pending"],
                                     font=('Segoe UI', 8, 'italic'))
        self.chat_display.tag_config("status_ack",
                                     foreground=self.colors["ack"],
                                     font=('Segoe UI', 8, 'italic'))
        self.chat_display.tag_config("system",
                                     foreground=self.colors["system"],
                                     font=('Segoe UI', 9, 'italic'),
                                     justify=tk.CENTER)

        # Input area
        input_frame = tk.Frame(self.root, bg=self.colors["bg"], height=80)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)
        input_frame.pack_propagate(False)

        entry_frame = tk.Frame(input_frame, bg=self.colors["input_bg"])
        entry_frame.pack(fill=tk.BOTH, expand=True)

        self.message_entry = tk.Entry(entry_frame,
                                      bg=self.colors["input_bg"],
                                      fg=self.colors["fg"],
                                      font=('Segoe UI', 11),
                                      borderwidth=0,
                                      highlightthickness=0,
                                      insertbackground=self.colors["fg"])
        self.message_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=15, pady=15)
        self.message_entry.bind('<Return>', lambda e: self._send_message())
        self.message_entry.focus()

        self.send_button = ttk.Button(entry_frame,
                                      text="Send",
                                      command=self._send_message)
        self.send_button.pack(side=tk.RIGHT, padx=15, pady=15)

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Welcome message
        self._display_system_message(f"Welcome to LoRa Chat, {self.username}!")
        self._display_system_message("Connecting to LoRa modem...")

    def _send_message(self):
        """Handle send button click."""
        content = self.message_entry.get().strip()
        if not content:
            return

        # Clear input
        self.message_entry.delete(0, tk.END)

        # Create message
        msg_id, payload = MessageProtocol.create_chat_message(self.username, content)
        msg = ChatMessage(msg_id, self.username, content, datetime.now().timestamp(), is_own=True)
        self.messages[msg_id] = msg
        self.pending_acks.add(msg_id)

        # Display message
        self._display_message(msg)

        # Send via LoRa
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._send_lora_message(payload), self.loop)

    async def _send_lora_message(self, payload: str):
        """Send message via LoRa."""
        if not self.lora_client:
            self._update_status("Not connected to LoRa", "error")
            return

        try:
            await self.lora_client.send_text(payload)
        except Exception as e:
            self._update_status(f"Send Error: {e}", "error")

    def _display_message(self, msg: ChatMessage):
        """Display a message in the chat window."""
        if not self.chat_display:
            return

        def _update():
            self.chat_display.config(state=tk.NORMAL)

            # Timestamp
            time_str = datetime.fromtimestamp(msg.timestamp).strftime("%H:%M")

            if msg.is_own:
                # Own message - right aligned
                self.chat_display.insert(tk.END, f"\n{time_str}  ", "timestamp")
                self.chat_display.insert(tk.END, f"{msg.content}  ", "own")

                # Status indicator
                status_text = " ✓ Sent" if not msg.acknowledged else f" ✓✓ Read"
                status_tag = "status" if not msg.acknowledged else "status_ack"
                self.chat_display.insert(tk.END, status_text, status_tag)
                self.chat_display.insert(tk.END, "\n")
            else:
                # Other's message - left aligned
                self.chat_display.insert(tk.END, f"\n@{msg.username}  ", "username")
                self.chat_display.insert(tk.END, f"{time_str}\n", "timestamp")
                self.chat_display.insert(tk.END, f"  {msg.content}  ", "other")
                self.chat_display.insert(tk.END, "\n")

            self.chat_display.config(state=tk.DISABLED)
            self.chat_display.see(tk.END)

        # Schedule UI update in main thread
        if self.root:
            self.root.after(0, _update)

    def _update_message_status(self, msg: ChatMessage, ack_username: str):
        """Update message status when ACK is received."""
        if not self.chat_display:
            return

        def _update():
            self.chat_display.config(state=tk.NORMAL)

            # Find and update the last status line
            # This is a simple approach - in production, you'd track positions
            content = self.chat_display.get("1.0", tk.END)
            lines = content.split('\n')

            # Look for the most recent status indicator
            for i in range(len(lines) - 1, -1, -1):
                if "✓ Sent" in lines[i] and msg.content in content:
                    # Update the display by redrawing (simple approach)
                    # For production, you'd want to track line positions
                    break

            self.chat_display.config(state=tk.DISABLED)
            self._update_status(f"Message read by {ack_username}", "success")

        if self.root:
            self.root.after(0, _update)

    def _display_system_message(self, text: str):
        """Display a system message."""
        if not self.chat_display:
            return

        def _update():
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.insert(tk.END, f"\n{text}\n", "system")
            self.chat_display.config(state=tk.DISABLED)
            self.chat_display.see(tk.END)

        if self.root:
            self.root.after(0, _update)

    def _update_status(self, message: str, status_type: str = "info"):
        """Update status bar."""
        if not self.status_label:
            return

        color_map = {
            "success": self.colors["ack"],
            "error": "#ff0000",
            "info": self.colors["system"]
        }

        def _update():
            self.status_label.config(text=message, fg=color_map.get(status_type, self.colors["system"]))

        if self.root:
            self.root.after(0, _update)

    def _on_closing(self):
        """Handle window close event."""
        self.running = False
        if self.loop:
            asyncio.run_coroutine_threadsafe(self._cleanup(), self.loop)

        # Give time for cleanup
        threading.Event().wait(0.5)

        if self.root:
            self.root.destroy()
