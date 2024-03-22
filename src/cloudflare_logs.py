import asyncio
import json
import logging
import requests
from typing import Optional, Union

import websockets

from src.syslog_client import SyslogTCPClient
from src.utils import EmailClient, LogClient


class CFClient:
    def __init__(self,
                 emailClient: EmailClient,
                 logClient: LogClient,
                 file_logger: logging.Logger,
                 ZONE_ID: str,
                 API_KEY: Union[str, None] = None,
                 EMAIL: Union[str, None] = None,
                 CLOUDFLARE_API_TOKEN: Union[str, None] = None, ):
        self.emailClient = emailClient
        self.file_logger = file_logger
        self.ZONE_ID = ZONE_ID
        self.API_KEY = API_KEY
        self.EMAIL = EMAIL
        self.CLOUDFLARE_API_TOKEN = CLOUDFLARE_API_TOKEN
        self.websocket_url = None
        self.logUtils = logClient

    async def _create_instant_logs_job(self):
        url = f"https://api.cloudflare.com/client/v4/zones/{self.ZONE_ID}/logpush/edge/jobs"

        if not self.ZONE_ID:
            raise ValueError("ZONE_ID is required to create an Instant Logs job.")

        # Determine the authentication method based on the available environment variables
        if self.API_KEY and self.EMAIL:
            headers = {
                "X-Auth-Email": self.EMAIL,
                "X-Auth-Key": self.API_KEY,
                "Content-Type": "application/json",
            }
        elif self.CLOUDFLARE_API_TOKEN:
            headers = {
                "Authorization": "Bearer " + self.CLOUDFLARE_API_TOKEN,
                "Content-Type": "application/json",
            }
        else:
            self.file_logger.error(
                "Authentication information is missing. Please provide an API key and email or an API token.")
            self.emailClient.send_email("Authentication information is missing for Cloudflare API.")
            return None

        data = {
            "fields": "ClientIP,ClientRequestHost,ClientRequestMethod,ClientRequestURI,EdgeEndTimestamp,"
                      "EdgeResponseBytes,EdgeResponseStatus,EdgeStartTimestamp,RayID",
            "sample": 1,
            "filter": "",
            "kind": "instant-logs"
        }

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 201:
            websocket_url = response.json()["result"]["destination_conf"]
            self.file_logger.info(f"WebSocket URL: {websocket_url}")
            self.websocket_url = websocket_url
        else:
            self.file_logger.error("Failed to create Instant Logs job")
            self.emailClient.send_email("Instant Logs Job Creation Failed")
            raise Exception(f"Failed to create Instant Logs job: {response.text}")

    async def connect_and_process_logs(self,
                                       syslog_client: Union[SyslogTCPClient, logging.Logger],
                                       syslog_type: str = 'native'):
        while True:
            ping_task = None  # Initialize ping_task to None outside the try block
            try:
                if not self.websocket_url:
                    await self._create_instant_logs_job()
                self.file_logger.info(f"Attempting to connect to WebSocket: {self.websocket_url}")
                async with websockets.connect(self.websocket_url) as websocket:
                    self.file_logger.info(f"Successfully connected to WebSocket!")
                    print(f"Successfully connected to WebSocket!")

                    async def send_ping():
                        while True:
                            try:
                                await websocket.ping()
                                await asyncio.sleep(60)  # Ping interval
                            except websockets.exceptions.ConnectionClosed:
                                break  # Exit the loop if the connection is closed

                    ping_task = asyncio.create_task(send_ping())

                    while True:
                        log_data = await websocket.recv()
                        # Split the received data into lines
                        log_lines = log_data.splitlines()
                        for log_line in log_lines:
                            try:
                                # Parse each line as a separate JSON object
                                log = json.loads(log_line)
                                # Ensure log is a dictionary before passing to convert_to_cef
                                if isinstance(log, dict):
                                    # Convert to CEF
                                    cef_log = self.logUtils.convert_to_cef(log)

                                    if syslog_type == 'native' and isinstance(syslog_client, logging.Logger):
                                        print(cef_log)
                                        # Handle syslog transmission
                                        syslog_client.handle(
                                            logging.LogRecord(
                                                "syslog_logger", logging.INFO, "", 0, cef_log, [], None
                                            )
                                        )
                                    else:
                                        syslog_client.send(cef_log)

                                    # Save log locally
                                    await self.logUtils.save_log_locally(log, cef_log)
                                else:
                                    self.file_logger.error(f"Received log entry is not in expected format: {log}")
                            except json.JSONDecodeError as e:
                                self.file_logger.error(f"Error decoding log line from JSON: {e}")
            except (websockets.ConnectionClosed, websockets.WebSocketException) as e:
                self.file_logger.error(f"WebSocket error: {e}")
                self.file_logger.error("WebSocket connection closed, attempting to reconnect...")
                await asyncio.sleep(5)  # Delay before attempting to reconnect
            except Exception as e:  # Catch-all for any other exceptions
                self.file_logger.error(f"An unexpected error occurred: {e}")
                break
            finally:
                if ping_task:
                    ping_task.cancel()  # Cancel the ping task if it's running
                    try:
                        await ping_task  # Wait for the task to be cancelled
                    except Exception as e:
                        pass  # Expected, as the task was cancelled
