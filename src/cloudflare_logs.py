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
            "fields": "BotScore,BotScoreSrc,ClientIP,ClientRequestHost,ClientRequestMethod,ClientRequestURI,"
                      "EdgeEndTimestamp,EdgeResponseStatus,EdgeStartTimestamp,RayID,ClientCountry,"
                      "ClientDeviceType,ClientRequestUserAgent,ClientIPClass,ClientRequestPath,ClientRequestProtocol,"
                      "ClientRequestReferer,ClientRequestSource,ClientXRequestedWith,ContentScanObjResults,"
                      "ContentScanObjTypes,EdgePathingOp,EdgePathingSrc,EdgePathingStatus,EdgeRequestHost,EdgeServerIP,"
                      "CacheCacheStatus,EdgeStartTimestamp,OriginIP,OriginResponseStatus,OriginSSLProtocol,"
                      "RequestHeaders,CacheResponseStatus,ResponseHeaders,SecurityAction,SecurityActions,"
                      "SecurityRuleDescription,SecurityRuleID,SecurityRuleIDs,SecuritySources,WAFFlags,WAFMatchedVar,"
                      "WAFRCEAttackScore,WAFSQLiAttackScore,WAFXSSAttackScore,ZoneName,ClientMTLSAuthStatus,"
                      "EdgeResponseContentType,ClientSSLCipher,ClientSSLProtocol,ClientSrcPort,OriginResponseBytes,"
                      "OriginResponseHTTPExpires,OriginResponseHTTPLastModified,OriginSSLProtocol,ParentRayID,"
                      "WorkerSubrequest,WorkerSubrequestCount,ZoneID,ClientRequestQuery,LeakedCredentialCheckResult,",
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
            error_message = f"Failed to create Instant Logs job: {response.text}"
            self.file_logger.error(error_message)
            self.emailClient.send_email("Instant Logs Job Creation Failed")
            raise Exception(error_message)

    async def connect_and_process_logs(self,
                                       syslog_client: Union[SyslogTCPClient, logging.Logger],
                                       syslog_type: str = 'native'):
        logger = logging.getLogger('websockets')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(logging.StreamHandler())
        while True:
            ping_task = None
            try:
                await self._create_instant_logs_job()  # Ensure we always have the latest websocket URL
                if not self.websocket_url:  # If we don't have a URL, wait a bit and try again
                    self.file_logger.error("WebSocket URL is not available. Will retry...")
                    await asyncio.sleep(10)
                    continue

                self.file_logger.info(f"Attempting to connect to WebSocket: {self.websocket_url}")
                async with websockets.connect(self.websocket_url) as websocket:
                    self.file_logger.info("Successfully connected to WebSocket!")
                    print("Successfully connected to WebSocket!")

                    async def send_ping():
                        while True:
                            try:
                                pong_waiter = await websocket.ping()
                                # Optionally wait for pong to measure latency
                                # latency = await pong_waiter
                                await asyncio.sleep(60)  # Ping interval
                            except websockets.exceptions.ConnectionClosed:
                                break  # Exit the loop if the connection is closed

                    ping_task = asyncio.create_task(send_ping())

                    while True:
                        try:
                            # Implementing timeout for recv using asyncio.wait_for
                            log_data = await asyncio.wait_for(websocket.recv(), timeout=10)
                            log_lines = log_data.splitlines()
                            for log_line in log_lines:
                                try:
                                    # Parse each line as a separate JSON object
                                    log = json.loads(log_line)
                                    # Ensure log is a dictionary before passing to convert to cef
                                    if isinstance(log, dict):
                                        # Convert to CEF
                                        cef_log = self.logUtils.convert_to_cef(log)

                                        if syslog_type == 'native' and isinstance(syslog_client, logging.Logger):
                                            print(cef_log)
                                            # Handle syslog transmission
                                            syslog_client.handle(
                                                logging.LogRecord(
                                                    "|", logging.INFO, "", 0, cef_log, [], None
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
                        except asyncio.TimeoutError:
                            self.file_logger.info("No data received within timeout period, continuing...")
                            continue
            except (websockets.ConnectionClosed, websockets.WebSocketException, websockets.ConnectionClosedError, websockets.ConnectionClosedOK) as e:
                self.file_logger.error(f"WebSocket error: {e}")
                self.file_logger.error("WebSocket connection closed, attempting to reconnect...")
                await asyncio.sleep(5)  # Delay before attempting to reconnect                
            except Exception as e:
                self.file_logger.error(f"An unexpected error occurred: {e}")
            finally:
                if ping_task:
                    ping_task.cancel()
                    try:
                        await ping_task
                    except asyncio.CancelledError:
                        pass  # Ping task cancellation is expected
                await self._create_instant_logs_job()  # Ensure we always have the latest websocket URL
                await asyncio.sleep(5)  # Delay before attempting to reconnect                