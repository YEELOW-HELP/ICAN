"""Download + extract the two official O*NET bulk text-database releases
this pass pins:

  * db_31_0_text.zip   — live scales (RIASEC / Work Style / Work Context)
  * db_30_2_text.zip   — Work Values only (removed from the DB in 30.3)

Direct file download from the O*NET Resource Center (no page scraping),
CC BY 4.0. Idempotent: skips a zip whose SHA-256 already matches, always
re-extracts so a partially-unpacked tree self-heals.

Usage:
    python -m scripts.onet_import.download_onet            # both releases
    python -m scripts.onet_import.download_onet --curl     # force system curl
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import zipfile

from scripts.onet_import.common import (
    ONET_DOWNLOAD_URL,
    VENDOR_DIR,
    LIVE_RELEASE,
    WORK_VALUES_RELEASE,
    log,
)

RELEASES = (LIVE_RELEASE, WORK_VALUES_RELEASE)


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest, use_curl: bool) -> None:
    if not use_curl:
        try:
            import requests  # noqa: PLC0415 — optional dep, see requirements-datalab.txt

            log(f"  GET {url}")
            with requests.get(url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                with open(dest, "wb") as fh:
                    for chunk in resp.iter_content(1 << 20):
                        fh.write(chunk)
            return
        except ImportError:
            log("  (requests not installed — falling back to curl)")

    log(f"  curl {url}")
    subprocess.run(["curl", "-sSL", "--fail", "-o", str(dest), url], check=True)


def main(argv: list[str]) -> int:
    use_curl = "--curl" in argv
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)

    for release in RELEASES:
        url = ONET_DOWNLOAD_URL.format(release=release)
        zip_path = VENDOR_DIR / f"db_{release}_text.zip"
        sha_path = zip_path.with_suffix(".zip.sha256")

        need_download = True
        if zip_path.exists() and sha_path.exists():
            if _sha256(zip_path) == sha_path.read_text().split()[0]:
                log(f"db_{release}: zip present and verified, skipping download")
                need_download = False

        if need_download:
            log(f"db_{release}: downloading")
            _download(url, zip_path, use_curl)
            digest = _sha256(zip_path)
            sha_path.write_text(f"{digest}  db_{release}_text.zip\n")
            log(f"db_{release}: sha256 {digest}")

        target = VENDOR_DIR / f"db_{release}_text"
        log(f"db_{release}: extracting -> {target}")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(target)

    log("done. next: python -m scripts.onet_import.build_onet_reference")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
