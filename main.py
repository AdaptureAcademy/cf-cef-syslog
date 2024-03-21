import asyncio
import os

from dotenv import load_dotenv

from src.cloudflare_logs import CFClient
from src.logging_config import setup_logging
from src.syslog_client import get_syslog_handler
from src.utils import EmailClient, LogClient

load_dotenv()

SYSLOG_SERVER = os.getenv("SYSLOG_ADDRESS")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT"))
SYSLOG_TYPE = os.getenv("SYSLOG_TYPE")

file_logger = setup_logging()
syslog_handler = get_syslog_handler(SYSLOG_SERVER, SYSLOG_PORT, syslog_type=SYSLOG_TYPE,
                                    con=os.getenv("SYSLOG_CONNECTION"))

log_client = LogClient(file_logger)
email_client = EmailClient(
    os.getenv("SMTP_SERVER"),
    os.getenv("RECIPIENTS"),
    os.getenv("SENDER_EMAIL"),
    os.getenv("EMAIL_PASSWORD"),
    os.getenv("EMAIL_SUBJECT"),
)

cf = CFClient(
    email_client,
    log_client,
    file_logger,
    os.getenv("ZONE_ID"),
    os.getenv("CLOUDFLARE_API_KEY"),
    os.getenv("CLOUDFLARE_EMAIL"),
    os.getenv("CLOUDFLARE_API_TOKEN"),
)


def exception_handler(loop, context):
    # Extracting the exception object
    exception = context.get('exception')
    if exception:
        file_logger.error(f"Caught exception: {exception}")
    else:
        file_logger.error(f"Caught exception: {context['message']}")


async def heartbeat(interval=60):
    """Logs a heartbeat message every `interval` seconds."""
    while True:
        file_logger.info("Heartbeat: script is running")
        print('Heartbeat: script is running')
        await asyncio.sleep(interval)


async def main():
    log_client.cleanup_old_logs('./log/cloudflare', retention_days=30)
    await cf.connect_and_process_logs(
        syslog_handler,
        SYSLOG_TYPE,
    )
    tasks = [
        asyncio.create_task(heartbeat(60)),
        asyncio.create_task(cf.connect_and_process_logs(syslog_handler, SYSLOG_TYPE))
    ]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main(), debug=True)
    except Exception as e:
        file_logger.error(f"Caught exception: {e}")
        email_client.send_email(f"Caught exception: {e}")
        raise e