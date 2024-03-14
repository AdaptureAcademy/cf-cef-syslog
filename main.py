import asyncio
import json
import logging.handlers
import os
import smtplib
import sys
from datetime import timezone
from email.message import EmailMessage

import dateutil.parser
import requests
import websockets
from dotenv import load_dotenv

print("Python %s on %s" % (sys.version, sys.platform))

# Load environment variables from .env
load_dotenv()

# Retrieve API key, email, and zone ID from environment variables
API_KEY = os.getenv("CLOUDFLARE_API_KEY")
EMAIL = os.getenv("CLOUDFLARE_EMAIL")
# BEARER = f"Bearer {os.getenv("CLOUDFLARE_BEARER")}""
ZONE_ID = os.getenv("ZONE_ID")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Syslog server configuration
SYSLOG_SERVER = "192.168.56.20"
SYSLOG_PORT = 514

# Path to the state file
STATE_FILE_PATH = "last_processed_timestamp.txt"

# Setup logging to syslog server
syslog_handler = logging.handlers.SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
syslog_handler.setLevel(logging.INFO)
syslog_logger = logging.getLogger("syslog_logger")
syslog_logger.addHandler(syslog_handler)
# Setup logging to file
formatter = logging.Formatter(fmt="%(asctime)s %(levelname)-8s %(message)s")
error_file_handler = logging.handlers.RotatingFileHandler(
    "error.log", maxBytes=10000, backupCount=10
)
error_file_handler.setLevel(logging.ERROR)
error_file_handler.setFormatter(formatter)
info_file_handler = logging.handlers.RotatingFileHandler(
    "info.log", maxBytes=15000, backupCount=10
)
info_file_handler.setLevel(logging.INFO)
info_file_handler.setFormatter(formatter)
file_logger = logging.getLogger("file_logger")
file_logger.addHandler(error_file_handler)
file_logger.addHandler(info_file_handler)


async def create_instant_logs_job():
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/logpush/edge/jobs"
    headers = {
        "X-Auth-Email": EMAIL,
        "X-Auth-Key": API_KEY,
        "Content-Type": "application/json",
    }
    data = {
        "fields": "ClientIP,ClientRequestHost,ClientRequestMethod,ClientRequestURI,EdgeEndTimestamp,EdgeResponseBytes,EdgeResponseStatus,EdgeStartTimestamp,RayID",
        "sample": 1,
        "filter": "",
        "kind": "instant-logs"
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        websocket_url = response.json()["result"]["destination_conf"]
        file_logger.info(f"WebSocket URL: {websocket_url}")
        return websocket_url
    else:
        file_logger.error("Failed to create Instant Logs job")
        send_email("Instant Logs Job Creation Failed")
        return None


async def connect_and_process_logs(websocket_url):
    async with websockets.connect(websocket_url) as websocket:
        try:
            while True:
                log_data = await websocket.recv()
                file_logger.info(f"Log data received: {log_data}")
                # Split the received data into lines
                log_lines = log_data.splitlines()
                print("Transforming and transmitting logs...")
                for log_line in log_lines:
                    try:
                        # Parse each line as a separate JSON object
                        log = json.loads(log_line)
                        # Ensure log is a dictionary before passing to convert_to_cef
                        if isinstance(log, dict):
                            # Convert to CEF
                            cef_log = convert_to_cef(log)
                            # Handle syslog transmission
                            syslog_logger.handle(
                                logging.LogRecord(
                                    "syslog_logger", logging.INFO, "", 0, cef_log, [], None
                                )
                            )
                            # Save log locally
                            await save_log_locally(log, cef_log)
                        else:
                            file_logger.error(f"Received log entry is not in expected format: {log}")
                    except json.JSONDecodeError as e:
                        file_logger.error(f"Error decoding log line from JSON: {e}")
        except websockets.exceptions.ConnectionClosed as e:
            file_logger.error(f"WebSocket connection closed: {e}")
            send_email("WebSocket Connection Closed")


async def save_log_locally(log, cef_log):
    # Use dateutil.parser.isoparse for compatibility with ISO 8601 formatted strings
    timestamp = dateutil.parser.isoparse(log["EdgeStartTimestamp"])

    # If your environment is set to use UTC and you want to ensure it, you can replace the timezone
    timestamp = timestamp.replace(tzinfo=timezone.utc)

    directory = f"./log/cloudflare/{timestamp.strftime('%Y')}/{timestamp.strftime('%B')}/{timestamp.strftime('%d')}"
    os.makedirs(directory, exist_ok=True)
    filepath = os.path.join(directory, f"{timestamp.strftime('%H')}:00.cef")

    with open(filepath, "a") as file:
        file.write(cef_log + "\n")

    print(f"Log saved locally: {filepath}")


def convert_to_cef(record: dict):
    # CEF:Version|Device Vendor|Device Product|Device Version|Device Event Class ID|Name|Severity|
    cef_header = "CEF:0|NetWitness|Audit|1.0|100|Log Received|1|"
    cef_mapping = {
        "src": record.get("ClientIP"),
        "dhost": record.get("ClientRequestHost"),
        "requestMethod": record.get("ClientRequestMethod"),
        "request": record.get("ClientRequestURI"),
        "end": record.get("EdgeEndTimestamp"),
        "bytesOut": record.get("EdgeResponseBytes"),
        "responseCode": record.get("EdgeResponseStatus"),
        "start": record.get("EdgeStartTimestamp"),
        "cn1": record.get("RayID"),
        "cn1Label": "RayID",
    }
    cef_record = cef_header + " ".join(
        f"{key}={value}" for key, value in cef_mapping.items() if value is not None
    )
    return cef_record


def send_email(text: str):
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    SENDER_EMAIL = "adapturetest@gmail.com"
    RECIPIENTS = ["cmartinez@adapture.com", "abaig@adapture.com"]
    msg = EmailMessage()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECIPIENTS)
    msg["Subject"] = "TESTING CELERY Catching Signals and Sending Emails"
    msg.set_content(text)
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Start TLS encryption
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
            print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")


# Main function to run the script
async def main():
    websocket_url = await create_instant_logs_job()
    if websocket_url:
        await connect_and_process_logs(websocket_url)


if __name__ == "__main__":
    asyncio.run(main())
