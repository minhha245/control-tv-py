"""
Python Bridge Server for Electron Key Detector
Receives key data from Electron and sends commands to Cubase
"""

import socket
import threading
import json
import time
import pyautogui
from typing import Optional, Callable

# Cubase key mapping coordinates (can be customized)
# These should be adjusted based on your Cubase setup
CUBASE_KEY_COORDS = {
    'C': (100, 200),
    'C#': (120, 200),
    'D': (140, 200),
    'D#': (160, 200),
    'E': (180, 200),
    'F': (200, 200),
    'F#': (220, 200),
    'G': (240, 200),
    'G#': (260, 200),
    'A': (280, 200),
    'A#': (300, 200),
    'B': (320, 200),
}


class CubaseBridge:
    """Bridge to control Cubase via automation"""

    def __init__(self):
        self.last_key = None
        self.last_scale = None

    def set_key(self, key: str, scale: str, confidence: float = 1.0) -> bool:
        """Set the key in Cubase"""
        try:
            if key == self.last_key and scale == self.last_scale:
                return True  # Already set

            print(f"[Cubase] Setting key: {key} {scale} (confidence: {confidence:.2f})")

            # TODO: Implement actual Cubase control
            # Options:
            # 1. Use AutoKey plugin coordinates
            # 2. Use MIDI CC to change key
            # 3. Use Cubase's remote control API

            # For now, just log the action
            self.last_key = key
            self.last_scale = scale

            return True

        except Exception as e:
            print(f"[Cubase] Error setting key: {e}")
            return False


class PythonBridgeServer:
    """TCP Server to receive commands from Electron"""

    def __init__(self, host: str = '127.0.0.1', port: int = 9999):
        self.host = host
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.is_running = False
        self.clients = []
        self.cubase_bridge = CubaseBridge()
        self.on_key_received: Optional[Callable] = None

    def start(self):
        """Start the bridge server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.is_running = True

            print(f"[Bridge] Server started on {self.host}:{self.port}")

            # Accept connections in a thread
            accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
            accept_thread.start()

        except Exception as e:
            print(f"[Bridge] Failed to start server: {e}")
            self.is_running = False

    def _accept_connections(self):
        """Accept incoming connections"""
        while self.is_running:
            try:
                client_socket, address = self.server_socket.accept()
                print(f"[Bridge] Client connected: {address}")

                self.clients.append(client_socket)

                # Handle client in a thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True
                )
                client_thread.start()

            except Exception as e:
                if self.is_running:
                    print(f"[Bridge] Accept error: {e}")

    def _handle_client(self, client_socket: socket.socket, address: tuple):
        """Handle messages from a client"""
        buffer = ""

        while self.is_running:
            try:
                data = client_socket.recv(4096)
                if not data:
                    break

                buffer += data.decode('utf-8')

                # Process complete messages (newline-separated)
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    self._process_message(message, client_socket)

            except Exception as e:
                print(f"[Bridge] Client error: {e}")
                break

        # Cleanup
        if client_socket in self.clients:
            self.clients.remove(client_socket)
        client_socket.close()
        print(f"[Bridge] Client disconnected: {address}")

    def _process_message(self, message: str, client_socket: socket.socket):
        """Process a message from a client"""
        try:
            data = json.loads(message)
            action = data.get('action')

            if action == 'set_key':
                key = data.get('key')
                scale = data.get('scale')
                confidence = data.get('confidence', 1.0)

                success = self.cubase_bridge.set_key(key, scale, confidence)

                # Notify callback
                if self.on_key_received:
                    self.on_key_received(key, scale, confidence)

                # Send response
                response = json.dumps({
                    'action': 'set_key_response',
                    'success': success,
                    'key': key,
                    'scale': scale
                })
                client_socket.send((response + '\n').encode('utf-8'))

            elif action == 'ping':
                response = json.dumps({'action': 'pong'})
                client_socket.send((response + '\n').encode('utf-8'))

        except json.JSONDecodeError as e:
            print(f"[Bridge] Invalid JSON: {e}")
        except Exception as e:
            print(f"[Bridge] Process error: {e}")

    def broadcast(self, message: dict):
        """Broadcast a message to all clients"""
        data = json.dumps(message) + '\n'
        for client in self.clients[:]:
            try:
                client.send(data.encode('utf-8'))
            except:
                self.clients.remove(client)

    def stop(self):
        """Stop the bridge server"""
        self.is_running = False

        # Close all clients
        for client in self.clients:
            try:
                client.close()
            except:
                pass

        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

        print("[Bridge] Server stopped")


def main():
    """Run the bridge server standalone"""
    print("=" * 50)
    print("   Electron Key Detector - Python Bridge")
    print("=" * 50)

    server = PythonBridgeServer()

    def on_key(key, scale, confidence):
        print(f">>> Key received: {key} {scale} ({confidence:.0%})")

    server.on_key_received = on_key
    server.start()

    try:
        print("\nWaiting for Electron app to connect...")
        print("Press Ctrl+C to stop\n")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
        server.stop()


if __name__ == '__main__':
    main()
