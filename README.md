# LoRa Chat Application
Simple, realtime chat that relies on LoRa to communicate. So you're using something off-grid, and is able to chat with
anyone who's in range (and is also using this same application). 

I know meshtastic exists, is light-years ahead of this, and is way more robust and feature-rich. 
However, I wanted to make something simple that would work, and I wanted to test my [Raspberry Pi Pico as a USB LoRa modem](https://github.com/brenordv/micropython-snippets/tree/master/pico_lora_sx1262) code.

## Installation
Ensure you have Python 3.13+ and install dependencies:

```bash
pip install pyserial
```

Or using uv:

```bash
uv sync
```

## Usage
### Starting the Application
```bash
python main.py <username> [port]
```

**Arguments:**
- `username` (required): Your chat username (2-20 characters)
- `port` (optional): Serial port for the LoRa modem (tries to auto-detected if not provided)

**Examples:**

```bash
# Auto-detect serial port
python main.py alice

# Specify serial port on Windows
python main.py bob COM8

# Specify serial port on Linux/Mac
python main.py charlie /dev/ttyACM0
```

### Using the Chat
1. **Send Messages**: Type your message in the input field and press Enter or click Send
2. **View Status**: 
   - ✓ Sent - Message transmitted via LoRa
   - ✓✓ Read - Message acknowledged by recipient
3. **Receive Messages**: Incoming messages appear automatically on the left side

## Architecture
### Message Protocol
Messages are JSON-formatted with two types:

**Chat Message:**
```json
{
  "type": "chat",
  "id": "abc123",
  "username": "alice",
  "content": "Hello World!",
  "timestamp": 1234567890.123
}
```

**Acknowledgment Message:**
```json
{
  "type": "ack",
  "ack_id": "abc123",
  "username": "bob",
  "timestamp": 1234567890.456
}
```

### ACK System
The application implements an informational ACK system:
- When a message is received, an automatic ACK is sent back
- ACKs update the sender's UI to show "Read" status (✓✓)
- ACKs are informational only - no errors are generated if ACKs are lost
- This is LoRa-friendly: acknowledges receipt without requiring reliability guarantees

### Threading Model
1. **Main Thread**: TKinter UI event loop
2. **Background Thread**: asyncio event loop for LoRa operations
3. **Thread-Safe Communication**: Messages passed between threads using asyncio primitives and TKinter's `after()` method

## Technical Details
### Dependencies
- **pyserial**: Serial port communication
- **asyncio**: Asynchronous I/O operations (built-in)
- **tkinter**: GUI framework (built-in)
- **json**: Message serialization (built-in)
