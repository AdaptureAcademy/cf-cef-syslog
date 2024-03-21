# src/utils.py
import os
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import smtplib
from typing import cast

import dateutil.parser


class EmailClient:
    def __init__(self, SMTP_SERVER, RECIPIENTS, SENDER_EMAIL=None, EMAIL_PASSWORD=None, EMAIL_SUBJECT=""):
        self.SMTP_SERVER = SMTP_SERVER
        self.SENDER_EMAIL = SENDER_EMAIL
        self.EMAIL_PASSWORD = EMAIL_PASSWORD
        self.SMTP_PORT = 587
        self.RECIPIENTS = 'abaig@adapture.com'
        self.EMAIL_SUBJECT = EMAIL_SUBJECT

    def send_email(self, text: str, subject: str = None):
        # Use the subject passed to the method; if None, use the instance variable
        email_subject = subject if subject is not None else self.EMAIL_SUBJECT

        # Ensure that the required credentials are set
        if not self.SENDER_EMAIL or not self.EMAIL_PASSWORD:
            print("Email credentials are missing. Please provide SMTP_SERVER, SENDER_EMAIL and EMAIL_PASSWORD.")
            return

        msg = EmailMessage()
        msg["From"] = self.SENDER_EMAIL
        msg["To"] = ",".join(self.RECIPIENTS)
        msg["Subject"] = email_subject
        msg.set_content(text)

        try:
            with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.starttls()  # Start TLS encryption
                server.login(self.SENDER_EMAIL, self.EMAIL_PASSWORD)
                server.send_message(msg)
                print("Email sent successfully")
        except Exception as e:
            print(f"Failed to send email: {str(e)}")


class LogClient:
    def __init__(self, file_logger):
        self.file_logger = file_logger

    def cleanup_old_logs(self, log_directory: str, retention_days: int):
        """Deletes log files older than retention_days in the specified directory."""
        current_time = datetime.now()
        for root, dirs, files in os.walk(log_directory, topdown=False):
            for name in files:
                file_path = os.path.join(root, name)
                file_path_str = cast(str, file_path)  # Explicitly cast to str if necessary
                file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path_str))
                if current_time - file_mod_time > timedelta(days=retention_days):
                    os.remove(file_path_str)
                    self.file_logger.info(f"Deleted old log file: {file_path_str}")
            for name in dirs:
                dir_path = os.path.join(root, name)
                dir_path_str = cast(str, dir_path)  # Explicitly cast to str if necessary
                if not os.listdir(dir_path_str):  # Check if the directory is empty
                    os.rmdir(dir_path_str)
                    self.file_logger.info(f"Deleted empty directory: {dir_path_str}")

    @staticmethod
    async def save_log_locally(log, cef_log):
        # Use dateutil.parser.isoparse for compatibility with ISO 8601 formatted strings
        timestamp = dateutil.parser.isoparse(log["EdgeStartTimestamp"])

        # If your environment is set to use UTC and you want to ensure it, you can replace the timezone
        timestamp = timestamp.replace(tzinfo=timezone.utc)

        directory = f"../log/cloudflare/{timestamp.strftime('%Y')}/{timestamp.strftime('%B')}/{timestamp.strftime('%d')}"
        os.makedirs(directory, exist_ok=True)
        filepath = os.path.join(directory, f"{timestamp.strftime('%H')}:00.cef")

        with open(filepath, "a") as file:
            file.write(cef_log + "\n")

        print(f"Log saved locally: {filepath}")

    @staticmethod
    def convert_to_cef(record: dict):
        cef_header = "CEF:0|Cloudflare|TrafficLogs|1.0.0|0.0|Log Received|1|"
        cef_mapping = {
            "src": record.get("ClientIP", ""),
            "dhost": record.get("ClientRequestHost", ""),
            "requestMethod": record.get("ClientRequestMethod", ""),
            "request": record.get("ClientRequestURI", "").replace("\n", "").replace("\r", "").replace("\t", " "),
            "end": record.get("EdgeEndTimestamp", ""),
            "bytesOut": str(record.get("EdgeResponseBytes", "")),
            "responseCode": str(record.get("EdgeResponseStatus", "")),
            "start": record.get("EdgeStartTimestamp", ""),
            "cn1": record.get("RayID", ""),
            "cn1Label": "RayID",
        }
        # Joining all parts together into one line
        cef_record_components = [f"{key}={value}" for key, value in cef_mapping.items() if value]
        cef_record = cef_header + ' '.join(cef_record_components)
        return cef_record + '/n'
