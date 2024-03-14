# Cloudflare Log Processor and Tester

This project consists of a Python script designed to fetch logs from Cloudflare, process them, and then save and transmit the logs in Common Event Format (CEF). Additionally, this README outlines the method for testing the script using Vagrant to simulate a syslog server and client environment.

## Overview

The Python script performs several key functions:
- Fetches logs from Cloudflare for specified time intervals.
- Processes and formats the logs into CEF.
- Saves the logs locally and transmits them to a syslog server.
- Handles errors and notifies via email if the script stops running or encounters an issue.

It also includes a mechanism to handle state between runs, storing the timestamp of the last processed log entry to ensure logs are not processed multiple times.

## Requirements

- Python 3.x
- `requests`, `python-dotenv`, `pytz`, and `python-dateutil` libraries
- A Cloudflare account with API access
- A `.env` file containing necessary API keys and other sensitive information
- A Vagrant environment for testing

## Setup

1. Ensure Python 3.x is installed on your system.
2. Install required Python libraries using `pip install requests python-dotenv pytz python-dateutil`.
3. Set up your `.env` file in the project root with the following variables:
   - `CLOUDFLARE_API_KEY`
   - `CLOUDFLARE_EMAIL`
   - `ZONE_ID`
   - `EMAIL_PASSWORD`
4. Ensure Vagrant is installed on your system.

## Testing with Vagrant

The included `Vagrantfile` configures two CentOS 7 virtual machines - one acting as a syslog client (running the Python script) and the other as a syslog server (receiving the logs).

### Steps:

1. Run `vagrant up` to start both the syslog client and server VMs.
2. SSH into the syslog client VM with `vagrant ssh syslog_client`.
3. Navigate to the script directory (if shared) or copy the script to the VM.
4. Run the script with `python3 <script_name>.py`.

### Syslog Server Configuration:

The syslog server is configured to listen on UDP port 514. The script sends logs to this server, where they can be reviewed for testing purposes.

## Script Delay and Real-Time Data Transmission

The script includes a one-minute delay between log processing intervals to manage load and ensure accuracy. However, for near real-time data transmission, it's possible to enhance the script with WebSocket support, enabling faster data transfer rates.

## Conclusion

This project provides a robust tool for Cloudflare log processing, coupled with a testing environment via Vagrant. Future enhancements may include WebSocket integration for improved data transmission speeds.
