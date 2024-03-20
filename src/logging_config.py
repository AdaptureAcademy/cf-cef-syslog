import logging.handlers


def setup_logging() -> logging.Logger:
    error_file_handler = logging.handlers.RotatingFileHandler(
        "error.log", maxBytes=10000, backupCount=10
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(logging.Formatter(fmt="%(asctime)s %(levelname)-8s %(message)s"))

    info_file_handler = logging.handlers.RotatingFileHandler(
        "info.log", maxBytes=15000, backupCount=10
    )
    info_file_handler.setLevel(logging.INFO)
    info_file_handler.setFormatter(logging.Formatter(fmt="%(asctime)s %(levelname)-8s %(message)s"))

    file_logger = logging.getLogger("file_logger")
    file_logger.setLevel(logging.DEBUG)
    file_logger.addHandler(error_file_handler)
    file_logger.addHandler(info_file_handler)

    return file_logger
