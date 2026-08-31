"""Download the official ESCO <-> O*NET-SOC crosswalk workbook."""

from __future__ import annotations

from data_explorer import config
from data_explorer.io import download


def run(*, use_curl: bool = False) -> None:
    dest = config.CROSSWALK_VENDOR_DIR / "ESCO_to_ONET-SOC.xlsx"
    download(config.CROSSWALK_URL, dest, use_curl=use_curl)
