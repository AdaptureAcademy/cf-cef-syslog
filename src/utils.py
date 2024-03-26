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
            "botScore": clean_string(record.get("BotScore", "")),
            "botScoreSrc": clean_string(record.get("BotScoreSrc", "")),
            "clientIP": clean_string(record.get("ClientIP", "")),
            "clientRequestHost": clean_string(record.get("ClientRequestHost", "")),
            "clientRequestMethod": clean_string(record.get("ClientRequestMethod", "")),
            "clientRequestURI": clean_string(record.get("ClientRequestURI", "")),
            "edgeEndTimestamp": clean_string(record.get("EdgeEndTimestamp", "")),
            "edgeResponseBytes": clean_string(record.get("EdgeResponseBytes", "")),
            "edgeResponseStatus": clean_string(record.get("EdgeResponseStatus", "")),
            "edgeStartTimestamp": clean_string(record.get("EdgeStartTimestamp", "")),
            "rayID": clean_string(record.get("RayID", "")),
            "clientCountry": clean_string(record.get("ClientCountry", "")),
            "clientDeviceType": clean_string(record.get("ClientDeviceType", "")),
            "clientRequestUserAgent": clean_string(record.get("ClientRequestUserAgent", "")),
            "clientIPClass": clean_string(record.get("ClientIPClass", "")),
            "clientRequestPath": clean_string(record.get("ClientRequestPath", "")),
            "clientRequestProtocol": clean_string(record.get("ClientRequestProtocol", "")),
            "clientRequestReferer": clean_string(record.get("ClientRequestReferer", "")),
            "clientRequestSource": clean_string(record.get("ClientRequestSource", "")),
            "clientXRequestedWith": clean_string(record.get("ClientXRequestedWith", "")),
            "contentScanObjResults": clean_string(record.get("ContentScanObjResults", "")),
            "contentScanObjTypes": clean_string(record.get("ContentScanObjTypes", "")),
            "edgePathingOp": clean_string(record.get("EdgePathingOp", "")),
            "edgePathingSrc": clean_string(record.get("EdgePathingSrc", "")),
            "edgePathingStatus": clean_string(record.get("EdgePathingStatus", "")),
            "edgeRequestHost": clean_string(record.get("EdgeRequestHost", "")),
            "edgeServerIP": clean_string(record.get("EdgeServerIP", "")),
            "cacheCacheStatus": clean_string(record.get("CacheCacheStatus", "")),
            "originIP": clean_string(record.get("OriginIP", "")),
            "originResponseStatus": clean_string(record.get("OriginResponseStatus", "")),
            "originSSLProtocol": clean_string(record.get("OriginSSLProtocol", "")),
            "requestHeaders": clean_string(record.get("RequestHeaders", "")),
            "cacheResponseStatus": clean_string(record.get("CacheResponseStatus", "")),
            "responseHeaders": clean_string(record.get("ResponseHeaders", "")),
            "securityAction": clean_string(record.get("SecurityAction", "")),
            "securityActions": clean_string(record.get("SecurityActions", "")),
            "securityRuleDescription": clean_string(record.get("SecurityRuleDescription", "")),
            "securityRuleID": clean_string(record.get("SecurityRuleID", "")),
            "securityRuleIDs": clean_string(record.get("SecurityRuleIDs", "")),
            "securitySources": clean_string(record.get("SecuritySources", "")),
            "wafFlags": clean_string(record.get("WAFFlags", "")),
            "wafMatchedVar": clean_string(record.get("WAFMatchedVar", "")),
            "wafRCEAttackScore": clean_string(record.get("WAFRCEAttackScore", "")),
            "wafSQLiAttackScore": clean_string(record.get("WAFSQLiAttackScore", "")),
            "wafXSSAttackScore": clean_string(record.get("WAFXSSAttackScore", "")),
            "zoneName": clean_string(record.get("ZoneName", "")),
            "clientMTLSAuthStatus": clean_string(record.get("ClientMTLSAuthStatus", "")),
            "edgeResponseContentType": clean_string(record.get("EdgeResponseContentType", "")),
            "clientSSLCipher": clean_string(record.get("ClientSSLCipher", "")),
            "clientSSLProtocol": clean_string(record.get("ClientSSLProtocol", "")),
            "clientSrcPort": clean_string(record.get("ClientSrcPort", "")),
            "edgeColoCode": clean_string(record.get("EdgeColoCode", "")),
            "edgeColoID": clean_string(record.get("EdgeColoID", "")),
            "edgeResponseCompressionRatio": clean_string(record.get("EdgeResponseCompressionRatio", "")),
            "originResponseBytes": clean_string(record.get("OriginResponseBytes", "")),
            "originResponseHTTPExpires": clean_string(record.get("OriginResponseHTTPExpires", "")),
            "originResponseHTTPLastModified": clean_string(record.get("OriginResponseHTTPLastModified", "")),
            "originResponseTime": clean_string(record.get("OriginResponseTime", "")),
            "parentRayID": clean_string(record.get("ParentRayID", "")),
            "workerCPUTime": clean_string(record.get("WorkerCPUTime", "")),
            "workerStatus": clean_string(record.get("WorkerStatus", "")),
            "workerSubrequest": clean_string(record.get("WorkerSubrequest", "")),
            "workerSubrequestCount": clean_string(record.get("WorkerSubrequestCount", "")),
            "zoneID": clean_string(record.get("ZoneID", "")),
            "clientRequestQuery": clean_string(record.get("clientRequestQuery", "")),
        }
        # Joining all parts together into one line
        cef_record_components = [f"{key}={value}" for key, value in cef_mapping.items() if value]
        cef_record = cef_header + ' '.join(cef_record_components)
        return cef_record + '\n'


def clean_string(string) -> str:
    if not isinstance(string, str):
        return string
    # Remove unwanted characters.
    cleaned_string = string.replace('\n', '').replace("\r", "").replace("\t", " ")
    # Enclose in quotes if the string contains spaces.
    if ' ' in cleaned_string:
        cleaned_string = f'"{cleaned_string}"'
    return cleaned_string
