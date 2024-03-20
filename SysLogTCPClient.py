import socket

class SyslogTCPClient:
    def __init__(self, server, port):
        self.server = server
        self.port = port
        self.sock = self._create_socket()

    def _create_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.server, self.port))
        return sock

    def send(self, message):
        try:
            print('Sent: ', message)
            self.sock.sendall(message.encode('utf-8'))
        except Exception as e:
            print(f"Error sending log to syslog: {e}")
            # Attempt to re-establish connection on error
            try:
                self.sock.close()
            except Exception:
                pass  # Ignore errors in closing the socket
            self.sock = self._create_socket()
            self.sock.sendall(message.encode('utf-8'))

    def close(self):
        self.sock.close()