import asyncio
import json
import logging.handlers
import os
import smtplib
import socket
import sys
from datetime import datetime, timedelta
from datetime import timezone
from email.message import EmailMessage
from typing import cast

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
ZONE_ID = os.getenv("ZONE_ID")

# Syslog server configuration
SYSLOG_SERVER = os.getenv("SYSLOG_ADDRESS")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT"))

# Setup logging to syslog server
syslog_handler = logging.handlers.SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT), socktype=socket.SOCK_STREAM)
syslog_handler.setLevel(logging.INFO)
syslog_logger = logging.getLogger("syslog_logger")
syslog_logger.addHandler(syslog_handler)
formatter = logging.Formatter('%(levelname)s - %(message)s')
syslog_handler.setFormatter(formatter)

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

    # Determine the authentication method based on the available environment variables
    if API_KEY and EMAIL:
        headers = {
            "X-Auth-Email": EMAIL,
            "X-Auth-Key": API_KEY,
            "Content-Type": "application/json",
        }
    elif os.getenv("CLOUDFLARE_API_TOKEN"):
        headers = {
            "Authorization": "Bearer " + os.getenv("CLOUDFLARE_API_TOKEN"),
            "Content-Type": "application/json",
        }
    else:
        file_logger.error("Authentication information is missing. Please provide an API key and email or an API token.")
        send_email("Authentication information is missing for Cloudflare API.")
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
        file_logger.info(f"WebSocket URL: {websocket_url}")
        return websocket_url
    else:
        file_logger.error("Failed to create Instant Logs job")
        send_email("Instant Logs Job Creation Failed")
        return None


def send_to_syslog(message):
    try:
        # Create a TCP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Connect to the syslog server
        sock.connect((SYSLOG_SERVER, SYSLOG_PORT))
        
        # Send the log message
        sock.sendall(message.encode())
        print(message.encode())
        # Close the socket
        sock.close()
    except Exception as e:
        file_logger.error(f"Error sending log to syslog: {e}")


async def connect_and_process_logs(websocket_url, attempt=1):
    try:
        file_logger.info(f"Attempting to connect to WebSocket: {websocket_url}")
        async with websockets.connect(websocket_url) as websocket:
            file_logger.info(f"Successfully connected to WebSocket on attempt {attempt}.")
            print(f"Successfully connected to WebSocket on attempt {attempt}.")
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
                            cef_log = convert_to_cef(log)
                            # Handle syslog transmission
                            # syslog_logger.handle(
                            #     logging.LogRecord(
                            #         "syslog_logger", logging.INFO, "", 0, cef_log, [], None
                            #     )
                            # )
                            send_to_syslog(cef_log)
                            # Save log locally
                            await save_log_locally(log, cef_log)
                        else:
                            file_logger.error(f"Received log entry is not in expected format: {log}")
                    except json.JSONDecodeError as e:
                        file_logger.error(f"Error decoding log line from JSON: {e}")
    except websockets.exceptions.ConnectionClosed:
        file_logger.error(f"Error connecting to WebSocket: {str(e)}")
        file_logger.error(f"WebSocket connection closed, attempting to reconnect... Attempt {attempt}")
        # cleanup_old_logs('./log/cloudflare', retention_days=30)
        print('Cleaned old logs...')
        if attempt <= 3:  # Set a maximum number of reconnection attempts
            await asyncio.sleep(10)  # Wait a bit before retrying
            new_websocket_url = await create_instant_logs_job()  # Recreate the Instant Logs job
            if new_websocket_url:
                await connect_and_process_logs(new_websocket_url, attempt + 1)
            else:
                send_email("Failed to recreate Instant Logs job for reconnection.")
        else:
            send_email("Exceeded maximum reconnection attempts for WebSocket session.")


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
    # Adjusted to ensure no extra space after CEF:0
    cef_header = f"CEF:0|Cloudflare|TrafficLogs|1.0.0|0.0|Log Received|1|"
    cef_mapping = {
        "src": record.get("ClientIP", ""),
        "dhost": record.get("ClientRequestHost", ""),
        "requestMethod": record.get("ClientRequestMethod", ""),
        "request": record.get("ClientRequestURI", ""),
        "end": record.get("EdgeEndTimestamp", ""),
        "bytesOut": str(record.get("EdgeResponseBytes", "")),
        "responseCode": str(record.get("EdgeResponseStatus", "")),
        "start": record.get("EdgeStartTimestamp", ""),
        "cn1": record.get("RayID", ""),
        "cn1Label": "RayID",
    }
    # Generate the CEF log string, ensuring no extra spaces are introduced
    cef_record_components = [f"{key}={value}" for key, value in cef_mapping.items() if value]
    cef_record = cef_header + ' '.join(cef_record_components)

    return cef_record


def cleanup_old_logs(log_directory: str, retention_days: int = 1):
    """Deletes log files older than retention_days in the specified directory."""
    current_time = datetime.now()
    for root, dirs, files in os.walk(log_directory, topdown=False):
        for name in files:
            file_path = os.path.join(root, name)
            file_path_str = cast(str, file_path)  # Explicitly cast to str if necessary
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path_str))
            if current_time - file_mod_time > timedelta(days=retention_days):
                os.remove(file_path_str)
                file_logger.info(f"Deleted old log file: {file_path_str}")
        for name in dirs:
            dir_path = os.path.join(root, name)
            dir_path_str = cast(str, dir_path)  # Explicitly cast to str if necessary
            if not os.listdir(dir_path_str):  # Check if the directory is empty
                os.rmdir(dir_path_str)
                file_logger.info(f"Deleted empty directory: {dir_path_str}")


def send_email(text: str):
    SMTP_SERVER = os.getenv('SMTP_SERVER')
    SMTP_PORT = 587
    SENDER_EMAIL = os.getenv('SENDER_EMAIL')
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

    # Ensure that the required environment variables are set
    if not SENDER_EMAIL or not EMAIL_PASSWORD or not SMTP_SERVER:
        print("Email credentials are missing. Please provide SMTP_SERVER, SENDER_EMAIL and EMAIL_PASSWORD in .env")
        return

    # Retrieve and process the recipient emails from .env
    recipients_str = os.getenv("EMAIL_RECIPIENTS", "")
    RECIPIENTS = recipients_str.split(",")  # Split the string into a list of emails

    msg = EmailMessage()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECIPIENTS)  # Use the list of emails
    msg["Subject"] = os.getenv("EMAIL_SUBJECT")
    msg.set_content(text)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Start TLS encryption
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
            print("Email sent successfully")
    except Exception as e:
        if not e:
            print("An unknown error occurred while sending the email.")
        else:
            print(f"Failed to send email: {str(e)}")


# Main function to run the script
async def main():
    websocket_url = await create_instant_logs_job()
    cleanup_old_logs('./log/cloudflare', retention_days=30)
    if websocket_url:
        await connect_and_process_logs(websocket_url)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def exception_handler(loop, context):
    # Extracting the exception object
    exception = context.get('exception')
    if exception:
        logger.error(f"Caught exception: {exception}")
    else:
        logger.error(f"Caught exception: {context['message']}")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(exception_handler)
    try:
        loop.run_until_complete(main())
    except Exception as e:
        if not e:
            print('An unknown error occurred')
        else:
            logger.error(f"Unhandled exception: {e}")
            send_email(f"Script crashed due to an unhandled exception: {str(e)}")
    finally:
        loop.close()
