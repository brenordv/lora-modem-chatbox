#!/usr/bin/env python3
"""
LoRa Chat Application - Main Entry Point

Usage:
    python main.py <username> [port]

Examples:
    python main.py alice
    python main.py bob COM8
    python main.py charlie /dev/ttyACM0
"""

import sys
from src.chatbox_app import ModernChatApp


def main():
    """Main entry point for the chat application."""
    
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Error: Username is required")
        print()
        print("Usage:")
        print("  python main.py <username> [port]")
        print()
        print("Examples:")
        print("  python main.py alice")
        print("  python main.py bob COM8")
        print("  python main.py charlie /dev/ttyACM0")
        sys.exit(1)
    
    username = sys.argv[1]
    port = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Validate username
    if not username or len(username) < 2:
        print("Error: Username must be at least 2 characters long")
        sys.exit(1)
    
    if len(username) > 20:
        print("Error: Username must be at most 20 characters long")
        sys.exit(1)
    
    # Start the application
    print(f"Starting LoRa Chat for user: {username}")
    if port:
        print(f"Using port: {port}")
    else:
        print("Auto-detecting serial port...")
    print()
    
    try:
        app = ModernChatApp(username=username, port=port)
        app.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

