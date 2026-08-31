"""MNP DATA EXPLORER command line.

    python -m data_explorer.cli download      # fetch O*NET + ESCO + crosswalk (idempotent)
    python -m data_explorer.cli build         # (re)build data/data_explorer/reference.sqlite
    python -m data_explorer.cli dictionary    # regenerate docs/data_explorer/{ONET,ESCO}_DATA_DICTIONARY.md
    python -m data_explorer.cli inventory     # regenerate docs/data_explorer/SOURCE_DATA_INVENTORY.md
    python -m data_explorer.cli analysis      # dimension analysis + data-quality report
    python -m data_explorer.cli golden        # export hand-authored human expected results -> golden fixtures
    python -m data_explorer.cli excel         # write MNP_ESCO_ONET_DATA_EXPLORER.xlsx
    python -m data_explorer.cli export-careers-excel   # write MNP_CAREER_KB_V1.xlsx (from the MNP Career KB)
    python -m data_explorer.cli refresh-workua-career-inventory   # re-crawl Work.ua Career Guide, diff, report (never touches the Career KB)
"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    use_curl = "--curl" in argv[1:]

    if cmd == "download":
        from data_explorer.crosswalk import download as x_dl
        from data_explorer.esco import download as e_dl
        from data_explorer.onet import download as o_dl
        o_dl.run(use_curl=use_curl)
        e_dl.run(use_curl=use_curl)
        x_dl.run(use_curl=use_curl)
    elif cmd == "build":
        from data_explorer import reference
        reference.build()
    elif cmd == "dictionary":
        from data_explorer.docs_gen import data_dictionary
        data_dictionary.write_all()
    elif cmd == "inventory":
        from data_explorer.docs_gen import source_inventory
        source_inventory.write()
    elif cmd == "analysis":
        from data_explorer.analysis import report
        report.run()
    elif cmd == "excel":
        from data_explorer.excel import workbook
        workbook.build()
    elif cmd == "export-careers-excel":
        from data_explorer.career_kb_export import export
        export.build()
    elif cmd == "refresh-workua-career-inventory":
        from data_explorer.workua import refresh
        print(refresh.run().as_report())
    elif cmd == "golden":
        from data_explorer.human_lab import golden_export
        golden_export.run()
    else:
        print(f"unknown command: {cmd}\n{__doc__}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
