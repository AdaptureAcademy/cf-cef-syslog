import json
import logging.handlers
import os
from datetime import datetime, timedelta
from dateutil import parser, tz
import requests
from dotenv import load_dotenv
import sys


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


def save_and_transmit_logs(logs):
    if not logs:
        return
    latest_log_timestamp = max(log['EdgeStartTimestamp'] for log in logs) / 1_000_000_000
    latest_timestamp = datetime.fromtimestamp(latest_log_timestamp, tz=tz.tzutc())

    for log in logs:
        cef_record = convert_to_cef(log)
        logger.info(cef_record)

        log_time = datetime.fromtimestamp(log['EdgeStartTimestamp'] / 1_000_000_000, tz=tz.tzutc())
        directory = f"./log/cloudflare/{log_time.strftime('%Y/%m/%d')}"
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, f"{log_time.strftime('%H')}.cef")

        with open(filepath, 'a') as file:
            file.write(cef_record + "\n")

    update_last_processed_timestamp(latest_timestamp)


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
        save_and_transmit_logs(logs)
        update_last_processed_timestamp(end_time)
        print("Logs have been processed.")
    else:
        print("No new logs to process.")


if __name__ == "__main__":
    main()
