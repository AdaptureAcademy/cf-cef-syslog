import asyncio
import os

from dotenv import load_dotenv

from src.cloudflare_logs import CFClient
from src.logging_config import setup_logging
from src.syslog_client import get_syslog_handler
from src.utils import EmailClient, LogClient

load_dotenv()

SYSLOG_SERVER = os.getenv("SYSLOG_SERVER")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT"))
SYSLOG_TYPE = os.getenv("SYSLOG_TYPE")

# pritn all os variables
print(
    os.getenv("SYSLOG_SERVER"),
    os.getenv('SYSLOG_PORT'),
    os.getenv('SYSLOG_TYPE'),
    os.getenv("SYSLOG_CONNECTION"),
    os.getenv("SMTP_SERVER"),
    os.getenv("RECIPIENTS"),
    os.getenv("SENDER_EMAIL"),
    os.getenv("EMAIL_PASSWORD"),
    os.getenv("EMAIL_SUBJECT"),
    os.getenv("ZONE_ID"),
    os.getenv("CLOUDFLARE_API_KEY"),
    os.getenv("CLOUDFLARE_EMAIL"),
    os.getenv("CLOUDFLARE_API_TOKEN"),
)

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
        await asyncio.sleep(interval)


# Modify your main function to include the heartbeat task
async def main():
    log_client.cleanup_old_logs('./log/cloudflare', retention_days=30)
    await cf.connect_and_process_logs(
        syslog_handler,
        SYSLOG_TYPE,
    )
    await asyncio.create_task(heartbeat(60))  # Adjust interval as needed
    print("Starting Cloudflare log processing")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    # Enable asyncio debug mode
    loop.set_debug(True)
    loop.set_exception_handler(exception_handler)
    try:
        loop.run_until_complete(main())
    except Exception as e:
        file_logger.error(f"Unhandled exception: {e}")
        email_client.send_email(f"Script crashed due to an unhandled exception: {str(e)}")
    finally:
        loop.close()
