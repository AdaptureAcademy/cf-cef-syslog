# Cloudflare Logger Setup Guide

This guide provides detailed instructions for deploying the Cloudflare Logger script on CentOS-based client machines. It covers setting up a virtual environment, installing dependencies, configuring the rsyslog server to receive logs, and running the script continuously using PM2. This script monitors the traffic on a Cloudflare account and sends logs to a remote syslog server in CEF format.

## Prerequisites

- A CentOS (or any Red Hat-based system) for both the client and server.
- Python 3.8 or higher installed on the client machine.
- Node.js installed on the client machine (for PM2 management).

## Setup Instructions


### 1. Create and Configure the .env File

Create a `.env` file in the project root with the following fields. Ensure to replace the placeholder values with your actual data:

```plaintext
SYSLOG_ADDRESS=192.168.56.20
SYSLOG_PORT=514

CLOUDFLARE_API_KEY=<your_cloudflare_api_key>
CLOUDFLARE_EMAIL=<your_cloudflare_email>

# Use EITHER CLOUDFLARE_API_KEY or CLOUDFLARE_API_TOKEN
CLOUDFLARE_API_TOKEN=<your_cloudflare_api_token>
ZONE_ID=<your_zone_id>

SENDER_EMAIL=<your_sender_email>
EMAIL_PASSWORD=<your_email_password>
EMAIL_RECIPIENTS=recipient1@example.com,recipient2@example.com
EMAIL_SUBJECT="Cloudflare Logs Job Alert"
```

### 2. Running the Script with PM2

Ensure you're in the script's directory, then start the script with PM2:

```bash
pm2 start "python3.8 main.py" --name "cf_logger" --max-memory-restart 1024M
pm2 save
pm2 startup
```

### 7. Stopping the script

Ensure you're in the script's directory, then stop the script with PM2:

```bash
pm2 stop cf_logger
```


### 3. Monitor and Restart the Script

- **To view logs:** `pm2 logs cf_logger`
- **To restart the script:** `pm2 restart cf_logger`

### 4. Monitor Syslog Messages

To monitor syslog messages on the server:

```bash
sudo tail -f /var/log/cef
```

## Documentation and Support

For further documentation and support, refer to the official PM2 and Python virtual environment documentation, or consult the Cloudflare API documentation for more details on the logging features used by this script.

---
