#!/usr/bin/env python
"""Pretty-print benchmark_data/benchmark_results.json (no rebuild required).

python scripts/print_benchmarks.py
python scripts/print_benchmarks.py --md          # markdown tables
python scripts/print_benchmarks.py --json PATH
make show-benchmarks
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "benchmark_data" / "benchmark_results.json"


def _load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"missing {path}\nRun: make benchmark && make benchmark-all")
    return json.loads(path.read_text(encoding="utf-8"))


def _s(sec: Optional[float]) -> str:
    if sec is None:
        return "—"
    if sec < 0.001:
        return f"{sec:.4f}s"
    if sec < 1:
        return f"{sec:.3f}s"
    return f"{sec:.3f}s"


def _mb(mb: float) -> str:
    return f"{mb:.1f} MB" if mb < 10 else f"{mb:.0f} MB"


def _rate(ev_s: Optional[float]) -> str:
    if not ev_s:
        return "—"
    if ev_s >= 1_000_000:
        return f"{ev_s / 1_000_000:.1f}M/s"
    if ev_s >= 1_000:
        return f"{ev_s / 1_000:.0f}k/s"
    return f"{ev_s:.0f}/s"


def _rel(rel: Optional[float]) -> str:
    if rel is None:
        return "—"
    if abs(rel - 1.0) < 0.05:
        return "1.00×"
    if rel > 1:
        return f"{rel:.2f}× slower"
    return f"{1 / rel:.2f}× faster"


def _hdr(title: str) -> str:
    bar = "═" * max(8, len(title) + 2)
    return f"\n{bar}\n {title}\n{bar}"


def _table(headers: List[str], rows: List[List[str]]) -> str:
    cols = list(zip(*([headers] + rows))) if rows else [tuple([h]) for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]

    def fmt(row: List[str]) -> str:
        return "  ".join(str(cell).ljust(w) for cell, w in zip(row, widths))

    sep = "  ".join("─" * w for w in widths)
    lines = [fmt(headers), sep]
    lines.extend(fmt(r) for r in rows)
    return "\n".join(lines)


def _backend_order(backends: Dict[str, Any]) -> List[str]:
    timed, rest = [], []
    for name, row in backends.items():
        if row and "seconds" in row:
            timed.append((row["seconds"], name))
        else:
            rest.append(name)
    timed.sort()
    names = [n for _, n in timed]
    if "xml_iterator" in names:
        names.remove("xml_iterator")
        names.insert(0, "xml_iterator")
    return names + rest


def _stream_rows(backends: Dict[str, Any]) -> List[List[str]]:
    rows = []
    for name in _backend_order(backends):
        row = backends.get(name) or {}
        if row.get("skipped") and "seconds" not in row:
            rows.append([name, "skipped", "—", "—", str(row["skipped"])[:40]])
            continue
        if "error" in row:
            rows.append([name, "ERROR", "—", "—", row["error"][:40]])
            continue
        rows.append(
            [
                name,
                _s(row.get("seconds")),
                f"{row.get('events', 0):,}",
                _rate(row.get("events_per_sec")),
                _rel(row.get("relative_to_xml_iterator")),
            ]
        )
    return rows


def print_pretty(data: Dict[str, Any]) -> None:
    stamps = [v.get("timestamp") for v in data.values() if isinstance(v, dict) and v.get("timestamp")]
    stamp = max(stamps) if stamps else "?"
    print(_hdr(f"xml_iterator benchmarks  ({stamp})"))

    # --- dict ---
    synth = sorted(
        (v for v in data.values() if isinstance(v, dict) and v.get("kind") == "synthetic_dict"),
        key=lambda r: r.get("n") or 0,
    )
    if synth:
        print("\nFull-document dict  (xml_to_dict vs xmltodict)")
        print(
            _table(
                ["n", "size", "xml_iterator", "xmltodict", "speedup"],
                [
                    [
                        f"{r['n']:,}",
                        _mb(r["file_size_mb"]),
                        _s(r["xml_iterator_full_seconds"]),
                        _s(r["xmltodict_full_seconds"]),
                        f"{r['speedup_factor']:.2f}×",
                    ]
                    for r in synth
                ],
            )
        )

    real_rows = []
    for key in ("SwissProt", "ESMA FIRDS"):
        r = data.get(key)
        if not isinstance(r, dict) or r.get("xml_iterator_full_seconds") is None:
            continue
        note = ""
        if r.get("results_identical") is True:
            note = "identical"
        elif r.get("results_identical") is False:
            note = "shape differs"
        sp = r.get("speedup_factor")
        real_rows.append(
            [
                r.get("dataset", key),
                _mb(r["file_size_mb"]),
                _s(r["xml_iterator_full_seconds"]),
                _s(r.get("xmltodict_full_seconds")),
                f"{sp:.2f}×" if sp is not None else "—",
                note,
            ]
        )
    if real_rows:
        print()
        print(
            _table(
                ["dataset", "size", "xml_iterator", "xmltodict", "speedup", "notes"],
                real_rows,
            )
        )

    early = data.get("Synthetic_early_exit")
    if isinstance(early, dict):
        print(
            f"\nEarly exit: first {early.get('max_events', 0):,} events = "
            f"{_s(early.get('stream_early_seconds'))}  vs full dict "
            f"{_s(early.get('xml_to_dict_seconds'))}  "
            f"(~{early.get('ratio_dict_over_early', 0):.0f}× — any streamer)"
        )

    # --- streams ---
    def stream_block(title: str, backends: Dict[str, Any]) -> None:
        print(f"\n{title}")
        print(
            _table(
                ["backend", "time", "events", "rate", "vs xml_iterator"],
                _stream_rows(backends),
            )
        )

    sc = data.get("Synthetic_stream_comparators")
    if isinstance(sc, dict) and sc.get("backends"):
        stream_block(
            f"Stream full drain — synthetic {sc.get('num_items', '?')} books ({_mb(sc.get('file_size_mb', 0))})",
            sc["backends"],
        )

    for key, label in (("SwissProt", "SwissProt"), ("ESMA FIRDS", "ESMA FIRDS")):
        r = data.get(key)
        if not isinstance(r, dict):
            continue
        size = _mb(r.get("file_size_mb", 0))
        if r.get("stream_comparators_full"):
            stream_block(f"Stream full drain — {label} ({size})", r["stream_comparators_full"])
        if r.get("stream_comparators_10k"):
            stream_block(f"Stream first 10k events — {label} ({size})", r["stream_comparators_10k"])

    print(
        "\nSAX “first N” is misleading: adapter buffers the whole parse first.\n"
        "Raw JSON + README: make readme-benchmarks · scripts/update_readme_benchmarks.py\n"
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", type=Path, default=DEFAULT_JSON, help="results JSON path")
    p.add_argument(
        "--md",
        action="store_true",
        help="print README-style markdown (uses bench_common; needs repo root on PYTHONPATH)",
    )
    args = p.parse_args()
    path = args.json if args.json.is_absolute() else (Path.cwd() / args.json)
    if not path.exists() and (ROOT / "benchmark_data" / "benchmark_results.json").exists():
        path = ROOT / "benchmark_data" / "benchmark_results.json"

    data = _load(path)

    if args.md:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from bench_common import render_benchmarks_section

        md = render_benchmarks_section(data)
        sys.stdout.write(md if md.endswith("\n") else md + "\n")
        return

    print_pretty(data)


if __name__ == "__main__":
    main()
