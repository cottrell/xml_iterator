#!/usr/bin/env python
"""Render benchmark markdown from benchmark_data/benchmark_results.json.

Usage:
  python scripts/update_readme_benchmarks.py           # patch README.md
  python scripts/update_readme_benchmarks.py --print    # stdout only
  python scripts/update_readme_benchmarks.py --json PATH --readme PATH
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bench_common import (  # noqa: E402
    README_PATH,
    RESULTS_PATH,
    load_results,
    render_benchmarks_section,
    update_readme_benchmarks,
)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="print markdown section to stdout; do not write README",
    )
    p.add_argument(
        "--json",
        type=Path,
        default=RESULTS_PATH,
        help=f"results JSON (default: {RESULTS_PATH})",
    )
    p.add_argument(
        "--readme",
        type=Path,
        default=README_PATH,
        help=f"README to patch (default: {README_PATH})",
    )
    args = p.parse_args()

    # load_results always uses RESULTS_PATH; allow override via cwd-relative copy
    if args.json.resolve() != (ROOT / RESULTS_PATH).resolve() and args.json.exists():
        import json

        data = json.loads(args.json.read_text(encoding="utf-8"))
    else:
        data = load_results()

    if not data:
        raise SystemExit(f"no results in {args.json} — run make benchmark / make benchmark-all first")

    md = render_benchmarks_section(data)
    if args.print_only:
        sys.stdout.write(md)
        if not md.endswith("\n"):
            sys.stdout.write("\n")
        return

    # Temporarily swap RESULTS if custom json was provided — section already rendered
    path = args.readme
    from bench_common import BENCH_BEGIN, BENCH_END

    block = f"{BENCH_BEGIN}\n{md.rstrip()}\n{BENCH_END}"
    text = path.read_text(encoding="utf-8")
    if BENCH_BEGIN not in text or BENCH_END not in text:
        # fall back to helper which can insert section
        update_readme_benchmarks(path)
        # re-apply with our rendered body if custom data
        text = path.read_text(encoding="utf-8")
    pre, rest = text.split(BENCH_BEGIN, 1)
    _, post = rest.split(BENCH_END, 1)
    path.write_text(pre + block + post, encoding="utf-8")
    print(f"updated {path} from {args.json}")


if __name__ == "__main__":
    main()
