import json
import logging.handlers
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser, tz
import requests
from dotenv import load_dotenv
import sys


# TODO:
# 1. Add error handling and logging
# 2. Logs are being duplicated in the log files. Need to fix this.

print('Python %s on %s' % (sys.version, sys.platform))
# Load environment variables from .env
load_dotenv()

# Retrieve API key, email, and zone ID from environment variables
API_KEY = os.getenv("CLOUDFLARE_API_KEY")
EMAIL = os.getenv("CLOUDFLARE_EMAIL")
ZONE_ID = os.getenv("ZONE_ID")

# Syslog server configuration
SYSLOG_SERVER = "localhost"
SYSLOG_PORT = 514

# Path to the state file
STATE_FILE_PATH = "last_processed_timestamp.txt"

# Setup logging to syslog server
syslog_handler = logging.handlers.SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(syslog_handler)


def get_last_processed_timestamp():
    try:
        with open(STATE_FILE_PATH, 'r') as file:
            last_processed_timestamp_str = file.read().strip()
            return parser.parse(last_processed_timestamp_str)
    except FileNotFoundError:
        return datetime.now(tz.tzutc()) - timedelta(hours=1)


def update_last_processed_timestamp(timestamp):
    with open(STATE_FILE_PATH, 'w') as file:
        file.write(timestamp.isoformat())


def fetch_cloudflare_logs(start_time, end_time):
    headers = {
        "X-Auth-Email": EMAIL,
        "X-Auth-Key": API_KEY,
        "Content-Type": "application/json",
    }
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/logs/received"
    params = {
        'start': start_time.isoformat(),
        'end': end_time.isoformat(),
        'fields': 'ClientIP,ClientRequestHost,ClientRequestMethod,ClientRequestURI,EdgeEndTimestamp,EdgeResponseBytes,EdgeResponseStatus,EdgeStartTimestamp,RayID',
    }
    response = requests.get(url, headers=headers, params=params)
    return [json.loads(line) for line in response.iter_lines(decode_unicode=True) if line]


def save_and_transmit_logs(logs, end_time):
    latest_timestamp = None  # Initialize variable to track the latest timestamp

    for record in logs:
        # Convert EdgeStartTimestamp to datetime object
        timestamp = datetime.fromtimestamp(record["EdgeStartTimestamp"] / 1_000_000_000.0, tz=timezone.utc)

        # Update latest_timestamp if this log's timestamp is newer
        if latest_timestamp is None or timestamp > latest_timestamp:
            latest_timestamp = timestamp

        # Directory structure and file handling remains the same
        directory = f"./var/log/cloudflare/{timestamp.strftime('%Y')}/{timestamp.strftime('%B')}/{timestamp.strftime('%d')}"
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, f"{timestamp.strftime('%H')}:00.cef")

        with open(filepath, 'a') as file:
            cef_record = convert_to_cef(record)
            # Transmit log to syslog server
            logger.info(cef_record)
            file.write(cef_record + "\n")

        # Optionally transmit log to syslog server
        # logger.info(cef_record)

    # Update the last_processed_timestamp to the end_time of this execution
    if logs:  # Update only if there are new logs processed
        update_last_processed_timestamp(end_time)


def convert_to_cef(record):
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
    cef_record = cef_header + " ".join(f"{key}={value}" for key, value in cef_mapping.items() if value is not None)
    return cef_record


def main():
    start_time = get_last_processed_timestamp()
    end_time = datetime.now(tz.tzutc()) - timedelta(minutes=1)

    if (end_time - start_time).total_seconds() > 3600:
        end_time = start_time + timedelta(hours=1)

    # logs = fetch_cloudflare_logs(start_time, end_time)

    # read logs from a json file
    with open('logs.json') as f:
        logs = json.load(f)

    if logs:
        save_and_transmit_logs(logs, end_time)
        update_last_processed_timestamp(end_time)
        print("Logs have been processed.")
    else:
        print("No new logs to process.")


if __name__ == "__main__":
    main()
