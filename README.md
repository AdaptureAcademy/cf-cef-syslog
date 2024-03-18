# Cloudflare Logger Setup Guide

This guide provides detailed instructions for deploying the Cloudflare Logger script on CentOS-based client machines. It covers setting up a virtual environment, installing dependencies, configuring the rsyslog server to receive logs, and running the script continuously using PM2. This script monitors the traffic on a Cloudflare account and sends logs to a remote syslog server in CEF format.

## Prerequisites

- A CentOS (or any Red Hat-based system) for both the client and server.
- Python 3.8 or higher installed on the client machine.
- Node.js installed on the client machine (for PM2 management).

## Setup Instructions

### 1. Clone the Script Repository

First, clone the repository containing the Cloudflare Logger script to your local machine:

```bash
git clone https://<username>:<github_PAT>@github.com/AdaptureAcademy/cf-cef-syslog.git --branch websocket-realtime
cd cf-cef-syslog
```

### 2. Install Node.js and PM2

Use `nvm` to install Node.js and then install PM2 globally:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.1/install.sh | bash
source ~/.bashrc
nvm install 15.0.1
nvm use 15.0.1
npm install pm2
```

### 3. Python Virtual Environment and Dependencies

Create and activate a Python virtual environment, then install the required dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure Syslog Server (Red Hat)

On the server machine, perform the following steps:

1. **Install rsyslog:**

   ```bash
   yum install -y rsyslog
   ```

2. **Configure rsyslog:**

   Edit `/etc/rsyslog.conf` to enable UDP listening:

   ```bash
   $ModLoad imudp
   $UDPServerRun 514
   ```

3. **Restart rsyslog and configure the firewall:**

   ```bash
   systemctl restart rsyslog
   firewall-cmd --permanent --add-port=514/udp
   firewall-cmd --reload
   ```

### 5. Create and Configure the .env File

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

### 6. Running the Script with PM2

Ensure you're in the script's directory, then start the script with PM2:

```bash
npx pm2 start "python3 main.py" --name "cloudflare_logger"
npx pm2 save
npx pm2 startup
```

### 7. Monitor and Manage the Script

- **To view logs:** `npx pm2 logs cloudflare_logger`
- **To stop the script:** `npx pm2 stop cloudflare_logger`
- **To restart the script:** `npx pm2 restart cloudflare_logger`

### 8. Monitor Syslog Messages

To monitor syslog messages on the server:

```bash
sudo tail -f /var/log/messages
```

## Documentation and Support

For further documentation and support, refer to the official PM2 and Python virtual environment documentation, or consult the Cloudflare API documentation for more details on the logging features used by this script.

---
