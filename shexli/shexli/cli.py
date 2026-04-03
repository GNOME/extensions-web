# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import argparse
import json
import sys

from .analyzer import analyze_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Static analysis for GNOME Shell extension packages"
    )
    parser.add_argument("path", help="Path to extension directory or ZIP archive")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args()

    result = analyze_path(args.path)
    if args.format == "json":
        json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    print(f"status: {result.summary['status']}")
    print(f"findings: {result.summary['finding_count']}")
    for finding in result.findings:
        print(f"[{finding.severity}] {finding.rule_id} {finding.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
