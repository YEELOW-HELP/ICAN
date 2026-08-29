"""Shared paths, version pins, O*NET element maps, and a tab-file reader
for the O*NET import pipeline.

Every O*NET element ID / scale ID below is taken verbatim from the
official release's own files (`Content Model Reference.txt`,
`Scales Reference.txt`) and cross-checked against
`methodology_lab/05_GOLDEN_TEST/MNP_SCALE_TO_ONET_MAPPING_V0.1.md` and the
M4.5 fixture (`app/services/career_kb/onet_30_3_numeric_fixture.py`) — it
is never inferred from the data values themselves.
"""

from __future__ import annotations

import csv
import sys
from collections.abc import Iterator
from pathlib import Path

# --------------------------------------------------------------------------
# Paths (all under the gitignored data/ tree except the committed artifact)
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
ONET_DIR = DATA_DIR / "onet"
VENDOR_DIR = ONET_DIR / "vendor"          # raw downloaded zips + extracted trees
REFERENCE_DB = ONET_DIR / "onet_reference.sqlite"
CROSSWALK_DIR = DATA_DIR / "crosswalks"
ATTRIBUTION_FILE = ONET_DIR / "ATTRIBUTION.md"

# The one committed output the application consumes (kept small: scoped to
# the O*NET-SOC codes an MNP career actually maps to).
SCOPED_SOURCE_ARTIFACT = REPO_ROOT / "app" / "services" / "career_kb" / "onet_source_v3.json"

# --------------------------------------------------------------------------
# Version pins (Founder decision, DATA-002 session)
# --------------------------------------------------------------------------
# Live scales (RIASEC / Work Style / Work Context) come from the current
# release; Work Values comes from the last release that still shipped the
# "Work Values.txt" file (removed from 30.3 onward).
LIVE_RELEASE = "31_0"                     # -> db_31_0_text.zip
LIVE_RELEASE_LABEL = "onet_31.0"
WORK_VALUES_RELEASE = "30_2"              # -> db_30_2_text.zip  (last with Work Values.txt)
WORK_VALUES_RELEASE_LABEL = "onet_30.2"

ONET_DOWNLOAD_URL = "https://www.onetcenter.org/dl_files/database/db_{release}_text.zip"

# CC BY 4.0 attribution text, verbatim from the release "Read Me.txt" / license page.
ONET_ATTRIBUTION = (
    "This product incorporates information from the O*NET Database "
    "(v31.0 for interests, work styles, and work context; v30.2 for work values), "
    "used under the Creative Commons Attribution 4.0 International License. "
    "O*NET is a trademark of the U.S. Department of Labor, Employment and Training "
    "Administration, National Center for O*NET Development."
)

# --------------------------------------------------------------------------
# O*NET Scale IDs (from Scales Reference.txt) and their official ranges.
# Asserted against the shipped Scales Reference.txt at build time.
# --------------------------------------------------------------------------
SCALE_RANGES: dict[str, tuple[float, float]] = {
    "OI": (1.0, 7.0),   # Occupational Interests (RIASEC)
    "WI": (-3.0, 3.0),  # Work Styles Impact (signed)
    "CX": (1.0, 5.0),   # Work Context (most elements)
    "CT": (1.0, 3.0),   # Work Context ("Work Schedules" only)
    "EX": (1.0, 7.0),   # Work Values Extent (30.2)
}

# --------------------------------------------------------------------------
# RIASEC: O*NET element ID -> letter (Career Interest Types.txt, scale OI)
# --------------------------------------------------------------------------
RIASEC_ELEMENTS: dict[str, str] = {
    "1.B.1.a": "R",
    "1.B.1.b": "I",
    "1.B.1.c": "A",
    "1.B.1.d": "S",
    "1.B.1.e": "E",
    "1.B.1.f": "C",
}

# --------------------------------------------------------------------------
# Work Style: O*NET element ID -> raw key used by the seed (Work Styles.txt,
# scale WI). `collaboration_*` are the two composite inputs the seed means
# into a single `collaboration` MNP scale (M4.5 precedent).
# `structure_preference` has NO current O*NET element (confirmed absent in
# 30.3 by M4.5 and re-confirmed absent in 31.0 by this pass) — deliberately
# not listed.
# --------------------------------------------------------------------------
WORK_STYLE_ELEMENTS: dict[str, str] = {
    "1.D.1.i": "leadership",
    "1.D.1.e": "initiative",
    "1.D.1.d": "ambiguity_tolerance",
    "1.D.2.f": "collaboration_social",
    "1.D.2.d": "collaboration_cooperation",
}

# --------------------------------------------------------------------------
# Work Context (-> MNP Work Environment scale). raw key -> (element ID, scale ID).
# `physical_environment_*` are the two composite inputs for `physical_environment`.
# (Work Context.txt: the row we want has Category == "n/a".)
# --------------------------------------------------------------------------
WORK_CONTEXT_ELEMENTS: dict[str, tuple[str, str]] = {
    "collaboration_context": ("4.C.1.b.1.e", "CX"),
    "customer_interaction_context": ("4.C.1.b.1.f", "CX"),
    "schedule_predictability": ("4.C.3.d.4", "CT"),
    "setting": ("4.C.2.a.1.a", "CX"),
    "physical_environment_standing": ("4.C.2.d.1.b", "CX"),
    "physical_environment_walking": ("4.C.2.d.1.d", "CX"),
}

# --------------------------------------------------------------------------
# Work Values (30.2 only): O*NET element ID -> MNP work_values scale key.
# ONLY the 3 DIRECT-mappable keys per MNP_SCALE_TO_ONET_MAPPING_V0.1.md §C.
# The other 5 MNP work_values keys (income, stability, growth,
# work_life_balance, learning) have NO O*NET counterpart and stay unsourced.
# --------------------------------------------------------------------------
WORK_VALUES_ELEMENTS: dict[str, str] = {
    "1.B.2.f": "independence_value",   # O*NET "Independence"
    "1.B.2.d": "impact_helping",       # O*NET "Relationships"
    "1.B.2.c": "recognition_status",   # O*NET "Recognition"
}


def extract_root(release: str) -> Path:
    """`data/onet/vendor/db_<release>_text/` — the folder the zip unpacks to."""
    return VENDOR_DIR / f"db_{release}_text" / f"db_{release}_text"


def find_release_dir(release: str) -> Path:
    """The directory that actually holds the .txt files for a release,
    tolerating the single- vs double-nested layout different unzip tools
    produce."""
    candidates = [
        VENDOR_DIR / f"db_{release}_text" / f"db_{release}_text",
        VENDOR_DIR / f"db_{release}_text",
        VENDOR_DIR / f"x{release}" / f"db_{release}_text",
    ]
    for c in candidates:
        if (c / "Read Me.txt").exists() or (c / "Occupation Data.txt").exists():
            return c
    raise FileNotFoundError(
        f"O*NET release {release} not found under {VENDOR_DIR}. "
        f"Run:  python -m scripts.onet_import.download_onet"
    )


def read_tab_file(path: Path) -> Iterator[dict[str, str]]:
    """Yield each data row of an O*NET tab-delimited file as a dict keyed by
    the header row. O*NET files are UTF-8, tab-separated, with a single
    header line and no quoting."""
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            yield row


def log(msg: str) -> None:
    print(msg, file=sys.stderr)
