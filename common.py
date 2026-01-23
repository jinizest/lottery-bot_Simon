import datetime
import logging
from datetime import timedelta

def setup_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

def get_search_date_range() -> dict:
    today = datetime.datetime.today()
    today_str = today.strftime("%Y%m%d")
    weekago = today - timedelta(days=7)
    weekago_str = weekago.strftime("%Y%m%d")
    return {
        "searchStartDate": weekago_str,
        "searchEndDate": today_str
    }

SLOTS = ["A", "B", "C", "D", "E"]
