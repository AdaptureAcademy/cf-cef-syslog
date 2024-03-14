import json
import logging.handlers
import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Retrieve API key, email, and zone ID from environment variables
API_KEY = os.getenv("CLOUDFLARE_API_KEY")
EMAIL = os.getenv("CLOUDFLARE_EMAIL")
ZONE_ID = os.getenv("ZONE_ID")

# Syslog server configuration
SYSLOG_SERVER = "localhost"
SYSLOG_PORT = 514

# Additions for state file functionality
STATE_FILE_PATH = "last_processed_timestamp.txt"

# Configure logging to syslog server
syslog_handler = logging.handlers.SysLogHandler(address=(SYSLOG_SERVER, SYSLOG_PORT))
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(syslog_handler)


def get_last_processed_timestamp():
    try:
        with open(STATE_FILE_PATH, 'r') as file:
            last_processed_timestamp = datetime.fromisoformat(file.read().strip())
    except FileNotFoundError:
        last_processed_timestamp = datetime.now(timezone.utc) - timedelta(hours=1)
    return last_processed_timestamp


def update_last_processed_timestamp(timestamp):
    with open(STATE_FILE_PATH, 'w') as file:
        file.write(timestamp.isoformat())


def fetch_cloudflare_logs(start_time: datetime, end_time: datetime):
    headers = {
        "X-Auth-Email": EMAIL,
        "X-Auth-Key": API_KEY,
        "Content-Type": "application/json",
    }
    url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/logs/received"
    params = {
        'start': start_time.isoformat(timespec='seconds'),  # Ensure ISO format with seconds precision
        'end': end_time.isoformat(timespec='seconds'),
        'fields': 'ClientIP,ClientRequestHost,ClientRequestMethod,ClientRequestURI,EdgeEndTimestamp,'
                  'EdgeResponseBytes,EdgeResponseStatus,EdgeStartTimestamp,RayID',
    }
    response = requests.get(url, headers=headers, params=params)
    return [json.loads(line) for line in response.iter_lines() if line]


def save_and_transmit_logs(logs):
    if not logs:
        return
    # Assuming logs are sorted by EdgeStartTimestamp
    latest_log_timestamp = max(log['EdgeStartTimestamp'] for log in logs) / 1_000_000_000
    latest_timestamp = datetime.fromtimestamp(latest_log_timestamp, tz=timezone.utc)

    for log in logs:
        cef_record = convert_to_cef(log)
        logger.info(cef_record)  # Transmit to syslog

        # Organize log files by date and hour
        log_time = datetime.fromtimestamp(log['EdgeStartTimestamp'] / 1_000_000_000, tz=timezone.utc)
        directory = f"./log/cloudflare/{log_time.strftime('%Y/%m/%d')}"
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, f"{log_time.strftime('%H')}.cef")

        with open(filepath, 'a') as file:
            file.write(cef_record + "\n")

    update_last_processed_timestamp(latest_timestamp)


def convert_to_cef(record):
    # Adjusting with CEF headers based on NetWitness requirements
    # CEF:Version|Device Vendor|Device Product|Device Version|Device Event Class ID|Name|Severity|
    cef_header = "CEF:0|NetWitness|Audit|1.0|100|Log Received|1|"

    # Mapping Cloudflare log fields to CEF fields according to NetWitness requirements
    cef_mapping = {
        "src": record.get("ClientIP"),  # Source IP
        "dhost": record.get("ClientRequestHost"),  # Destination Hostname
        "requestMethod": record.get("ClientRequestMethod"),  # HTTP Method
        "request": record.get("ClientRequestURI"),  # Request URI
        "end": record.get("EdgeEndTimestamp"),  # End Timestamp
        "bytesOut": record.get("EdgeResponseBytes"),  # Response Bytes
        "responseCode": record.get("EdgeResponseStatus"),  # HTTP Response Status Code
        "start": record.get("EdgeStartTimestamp"),  # Start Timestamp
        "cn1": record.get(
            "RayID"
        ),  # Custom field, as RayID does not directly map to a NetWitness field
        "cn1Label": "RayID",  # Label for the custom field
    }

    # Format the CEF record by iterating over the cef_mapping dictionary
    # and concatenating each key-value pair in the 'key=value' format.
    # We also include spaces between each pair as per the CEF specification.
    cef_record = cef_header + " ".join(
        f"{key}={value}" for key, value in cef_mapping.items() if value is not None
    )
    return cef_record


def main():
    start_time = get_last_processed_timestamp()
    end_time = datetime.now(timezone.utc) - timedelta(minutes=1)

    # Ensure end_time is not more than 1 hour ahead of start_time
    if (end_time - start_time).total_seconds() > 3600:
        end_time = start_time + timedelta(hours=1)

    logs = fetch_cloudflare_logs(start_time, end_time)

    if logs:
        save_and_transmit_logs(logs)
        # Update the last processed timestamp to the end_time of this execution
        update_last_processed_timestamp(end_time)
        print("Logs have been processed.")
    else:
        print("No new logs to process.")


if __name__ == "__main__":
    main()
