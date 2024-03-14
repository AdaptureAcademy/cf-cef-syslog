import json
import logging.handlers
import os
from datetime import datetime, timedelta, timezone
from dateutil import tz, parser as date_parser
import requests
from dotenv import load_dotenv
import sys
import smtplib
from email.message import EmailMessage

# TODO:
# 1. Email Notification if script stops running or throws an error

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
SYSLOG_SERVER = "customhost"  # "192.168.56.20"  # "customhost"
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


def get_last_processed_timestamp():
    try:
        with open(STATE_FILE_PATH, "r") as file:
            last_processed_timestamp_str = file.read().strip()
            return date_parser.parse(last_processed_timestamp_str)
    except FileNotFoundError:
        file_logger.info("State file not found. Assuming first run.")
        return datetime.now(tz.tzutc()) - timedelta(hours=1)


def update_last_processed_timestamp(timestamp):
    # chek if STATE_FILE_PATH exists and log the first time it is created
    if not os.path.exists(STATE_FILE_PATH):
        file_logger.info(f"Creating file {STATE_FILE_PATH}")
    with open(STATE_FILE_PATH, "w") as file:
        file.write(timestamp.isoformat())


def fetch_cloudflare_logs(start_time: datetime, end_time: datetime):
    headers = {
        "X-Auth-Email": EMAIL,
        "X-Auth-Key": API_KEY,
        "Content-Type": "application/json",
    }
    # headers = {
    #     "Authentication": BEARER,
    #     "Content-Type": "application/json",
    # }
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/logs/received"
    params = {
        "start": start_time.isoformat(),
        "end": end_time.isoformat(),
        "fields": "ClientIP,ClientRequestHost,ClientRequestMethod,ClientRequestURI,EdgeEndTimestamp,EdgeResponseBytes,EdgeResponseStatus,EdgeStartTimestamp,RayID",
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        file_logger.error(f"Failed to fetch logs: {e}")
        return []
    return [
        json.loads(line) for line in response.iter_lines(decode_unicode=True) if line
    ]


def save_and_transmit_logs(logs, end_time):
    try:
        latest_timestamp = None  # Initialize variable to track the latest timestamp

        for record in logs:
            # Convert EdgeStartTimestamp to datetime object
            timestamp = datetime.fromtimestamp(
                record["EdgeStartTimestamp"] / 1_000_000_000.0, tz=timezone.utc
            )

            # Update latest_timestamp if this log's timestamp is newer
            if latest_timestamp is None or timestamp > latest_timestamp:
                latest_timestamp = timestamp

            # Directory structure and file handling remains the same
            directory = f"./log/cloudflare/{timestamp.strftime('%Y')}/{timestamp.strftime('%B')}/{timestamp.strftime('%d')}"
            os.makedirs(directory, exist_ok=True)
            filepath = os.path.join(directory, f"{timestamp.strftime('%H')}:00.cef")
            cef_record = convert_to_cef(record)

            # Log to syslog server and file
            syslog_handler.handle(
                logging.LogRecord(
                    "syslog_logger", logging.INFO, filepath, 0, cef_record, [], None
                )
            )
            with open(filepath, "a") as file:
                file.write(cef_record + "\n")

        # Update the last_processed_timestamp to the end_time of this execution
        if logs:  # Update only if there are new logs processed
            update_last_processed_timestamp(end_time)
    except Exception as e:
        file_logger.error("An error occurred while saving logs", exc_info=True)
        syslog_logger.error("An error occurred while saving logs", exc_info=True)
        # email notification to be added
        raise e


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
    SENDER_PASSWORD = "qavz tjug vfjr mcki"
    RECIPIENTS = ["cmartinez@adapture.com", "abaig@adapture.com"]
    msg = EmailMessage()
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECIPIENTS)
    msg["Subject"] = "TESTING CELERY Catching Signals and Sending Emails"
    msg.set_content(text)
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Start TLS encryption
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
            print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")


def main():
    try:
        current_time = datetime.now(tz.tzutc())
        last_processed_time = get_last_processed_timestamp()

        # Loop through each hour from the last_processed_time up to the current_time
        while last_processed_time < current_time:
            # Calculate the start and end time for the current hour block
            start_time = last_processed_time
            end_time = min(start_time + timedelta(hours=1), current_time)

            # Update last_processed_time for the next iteration
            last_processed_time = end_time

            # Fetch logs for the current hour block
            logs = fetch_cloudflare_logs(start_time, end_time)

            # Process and save the logs
            if logs:
                save_and_transmit_logs(logs, end_time)
                # Update the last_processed_timestamp to the end_time of this hour block
                update_last_processed_timestamp(end_time)
                print(f"Logs between {start_time} and {end_time} have been processed.")
            else:
                print(f"No new logs to process between {start_time} and {end_time}.")

    except Exception as e:
        file_logger.error("An error occurred", exc_info=True)
        syslog_logger.error("An error occurred", exc_info=True)
        # email notification to be added
        raise e


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        send_email(f"An error occurred: {str(e)}")
        pass
