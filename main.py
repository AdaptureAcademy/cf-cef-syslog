import json
import logging.handlers
import os
from datetime import datetime, timedelta, timezone
from dateutil import tz, parser as date_parser
import requests
from dotenv import load_dotenv
import sys

# TODO:
# 1. Add error handling and logging
# 2. Logs are being duplicated in the log files. Need to fix this.

print("Python %s on %s" % (sys.version, sys.platform))
# Load environment variables from .env
load_dotenv()

# Retrieve API key, email, and zone ID from environment variables
API_KEY = os.getenv("CLOUDFLARE_API_KEY")
EMAIL = os.getenv("CLOUDFLARE_EMAIL")
# BEARER = f"Bearer {os.getenv("CLOUDFLARE_BEARER")}""
ZONE_ID = os.getenv("ZONE_ID")

# Syslog server configuration
SYSLOG_SERVER = "192.168.56.20"
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
        with open(STATE_FILE_PATH, "r") as file:
            last_processed_timestamp_str = file.read().strip()
            return date_parser.parse(last_processed_timestamp_str)
    except FileNotFoundError:
        return datetime.now(tz.tzutc()) - timedelta(hours=1)


def update_last_processed_timestamp(timestamp):
    with open(STATE_FILE_PATH, "w") as file:
        file.write(timestamp.isoformat())


def fetch_cloudflare_logs(start_time, end_time):
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
    response = requests.get(url, headers=headers, params=params)
    return [
        json.loads(line) for line in response.iter_lines(decode_unicode=True) if line
    ]


def save_and_transmit_log_file(logs: list, end_time: datetime):
    directory = f"./var/log/cloudflare/{end_time.strftime('%Y')}/{end_time.strftime('%B')}/{end_time.strftime('%d')}"
    os.makedirs(directory, exist_ok=True)
    filepath = os.path.join(directory, f"{end_time.strftime('%H')}:00.cef")

    with open(filepath, "a") as file:
        for record in logs:
            cef_record = convert_to_cef(record)
            file.write(cef_record + "\n")

    # Transmit log to syslog server
    # logger.info(cef_record)


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


def main():
    start_time = get_last_processed_timestamp()
    end_time = datetime.now(tz.tzutc()) - timedelta(minutes=1)

    if (end_time - start_time).total_seconds() > 3600:
        end_time = start_time + timedelta(hours=1)

    # logs = fetch_cloudflare_logs(start_time, end_time)

    # read logs from a json file
    with open("logs.json") as f:
        logs = json.load(f)

    if logs:
        save_and_transmit_log_file(logs, end_time)
        update_last_processed_timestamp(end_time)
        print("Logs have been processed.")
    else:
        print("No new logs to process.")


if __name__ == "__main__":
    main()
