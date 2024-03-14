# Cloudflare Log Transformation and Transmission

## Overview
This Python script is designed to fetch, transform, and transmit Cloudflare log data in real-time. Utilizing Cloudflare's Logpush service and a WebSocket connection, the script converts incoming log data to the Common Event Format (CEF) and forwards it to a configured syslog server. Additionally, logs are saved locally in a structured directory format.

## Features
- **WebSocket Connection:** Real-time log data fetching from Cloudflare.
- **Log Transformation:** Converts log data to CEF for standardized processing.
- **Syslog Transmission:** Forwards transformed logs to a syslog server.
- **Local Log Storage:** Saves log data locally for backup and further analysis.
- **Error Handling:** Notifications via email for critical failures or service interruptions.

## Requirements
- Python 3.10 or higher.
- `websockets`, `requests`, `python-dotenv`, `dateutil` libraries.
- Access to Cloudflare API with valid credentials.
- A configured `.env` file with necessary API keys and configurations.

## Setup Instructions
1. Ensure Python and pip are installed on your system.
2. Clone this repository or download the script.
3. Install required Python libraries:
   ```
   pip install websockets requests python-dotenv python-dateutil
   ```
4. Create a `.env` file in the root directory with the following keys:
   ```
   CLOUDFLARE_API_KEY=your_cloudflare_api_key
   CLOUDFLARE_EMAIL=your_cloudflare_email
   ZONE_ID=your_zone_id
   EMAIL_PASSWORD=your_email_password
   ```
5. Adjust the syslog server settings in the script as needed.

## Testing with Vagrant and CentOS
The included Vagrantfile configures a testing environment with two CentOS 7 VMs - one acting as the syslog client (running this script) and the other as the syslog server.

### Steps:
1. Install Vagrant and VirtualBox.
2. Run `vagrant up` to initialize and start the VMs.
3. SSH into the syslog client VM: `vagrant ssh syslog_client`.
4. Set up your environment and run the script inside the VM.

### Syslog Server Configuration:
- Pre-configured to listen on UDP port 514.
- Validates real-time log forwarding and local storage.
- Allows for the testing of the script's full functionality in a controlled environment.

## Usage
Run the script with:
```
python3 main.py
```

Logs are fetched from Cloudflare, converted to CEF, transmitted to the specified syslog server, and saved locally in a structured directory format. Email notifications will be sent for critical errors or interruptions.
