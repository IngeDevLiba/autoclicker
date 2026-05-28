"""
Per-account activity logger.

Each account gets its own CSV log file under the LOG_DIR directory.
Columns: date, account, keyword, url, dwell_seconds
"""

import csv
import os
from datetime import datetime
from config import LOG_DIR, LOG_DATE_FORMAT

_FIELDS = ["date", "account", "keyword", "url", "dwell_seconds"]


def _log_path(account: str) -> str:
    """Return the path of the CSV log file for *account*."""
    os.makedirs(LOG_DIR, exist_ok=True)
    safe_name = account.replace("@", "_at_").replace("/", "_").replace("\\", "_")
    return os.path.join(LOG_DIR, f"{safe_name}.csv")


def log_action(
    account: str,
    keyword: str,
    url: str,
    dwell_seconds: float,
) -> None:
    """
    Append one row to the account's CSV log.

    Parameters
    ----------
    account:       Account identifier (e.g. an e-mail address).
    keyword:       The search term that was typed.
    url:           The URL that was visited (search result or article).
    dwell_seconds: How long (seconds) the browser stayed on the page.
    """
    path = _log_path(account)
    file_exists = os.path.isfile(path)

    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "date": datetime.now().strftime(LOG_DATE_FORMAT),
                "account": account,
                "keyword": keyword,
                "url": url,
                "dwell_seconds": round(dwell_seconds, 1),
            }
        )
