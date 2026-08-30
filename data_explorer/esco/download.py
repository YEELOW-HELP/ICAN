"""Download + extract the pinned ESCO classification CSV bundles
(English + Ukrainian).

Free of charge, open. Direct file download from the EU ESCO service
(no scraping). Idempotent (sha256-cached).
"""

from __future__ import annotations

from data_explorer import config
from data_explorer.io import download, extract_zip, log


def run(*, use_curl: bool = False) -> None:
    for lang in config.ESCO_LANGUAGES:
        url = config.ESCO_URL.format(version=config.ESCO_VERSION, lang=lang)
        zip_path = config.ESCO_VENDOR_DIR / f"esco_{config.ESCO_VERSION}_classification_{lang}_csv.zip"
        download(url, zip_path, use_curl=use_curl)
        target = config.ESCO_VENDOR_DIR / f"esco_{config.ESCO_VERSION}_classification_{lang}_csv"
        log(f"  extract ESCO {config.ESCO_VERSION} {lang} -> {target}")
        extract_zip(zip_path, target)
