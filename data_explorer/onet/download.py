"""Download + extract the two pinned O*NET bulk text-database releases.

  * db_31_0_text.zip  — live occupational data
  * db_30_2_text.zip  — Work Values only (removed from the DB in 30.3)

CC BY 4.0. Direct file download from the O*NET Resource Center, no page
scraping. Idempotent (sha256-cached).
"""

from __future__ import annotations

from data_explorer import config
from data_explorer.io import download, extract_zip, log


def run(*, use_curl: bool = False) -> None:
    for release in (config.ONET_RELEASE, config.ONET_WORK_VALUES_RELEASE):
        url = config.ONET_URL.format(release=release)
        zip_path = config.ONET_VENDOR_DIR / f"db_{release}_text.zip"
        download(url, zip_path, use_curl=use_curl)
        target = config.ONET_VENDOR_DIR / f"db_{release}_text"
        log(f"  extract db_{release}_text -> {target}")
        extract_zip(zip_path, target)
