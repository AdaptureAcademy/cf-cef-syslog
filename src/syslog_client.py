import logging.handlers
import socket
from logging import Logger
from typing import Union


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
            self.sock.sendall(message.encode('utf-8'))
            print('Sent: ', (message).encode('utf-8'))
        except Exception as e:
            print(f"Error sending log to syslog: {e}. Attempting to reconnect and resend.")

            # Cleanly close the existing socket before trying to reconnect
            self.close()  # Use the close method for proper resource management

            # Re-establish the connection
            self._create_socket_and_reconnect()

            # Try to send the message again after reconnecting.
            try:
                self.sock.sendall(message.encode('utf-8'))
                print('Sent after reconnect: ', message)
            except Exception as e:
                # If sending fails again after reconnecting, log the error
                print(f"Error sending log to syslog after reconnecting: {e}. Giving up.")
                raise e

    def close(self):
        """Safely close the socket connection."""
        try:
            self.sock.close()
        except Exception as e:
            # Log or print the error when attempting to close the socket.
            print(f"Error closing the socket: {e}")
            raise e

    def _create_socket_and_reconnect(self):
        """Create a new socket and attempt to reconnect to the server."""
        self.sock = self._create_socket()
        try:
            self.sock.connect((self.server, self.port))
        except Exception as e:
            # Handle potential errors during the reconnection attempt.
            print(f"Failed to reconnect to the syslog server: {e}")
            raise e

def get_syslog_handler(SYSLOG_SERVER, SYSLOG_PORT, syslog_type: str = 'native', con: str = 'udp') \
        -> Union[Logger, SyslogTCPClient]:
    if syslog_type == 'native':
        # Setup logging to syslog server
        if con == 'tcp':
            print('Server: ', SYSLOG_SERVER)
            syslog_handler = logging.handlers.SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT),
                                                            socktype=socket.SOCK_STREAM)
        else:
            syslog_handler = logging.handlers.SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))

        syslog_handler.setLevel(logging.INFO)
        syslog_logger = logging.getLogger("syslog_logger")
        syslog_logger.addHandler(syslog_handler)

        formatter = logging.Formatter('%(message)s')
        syslog_handler.setFormatter(formatter)

        return syslog_logger
    else:
        syslog_client = SyslogTCPClient(SYSLOG_SERVER, SYSLOG_PORT)
        return syslog_client
