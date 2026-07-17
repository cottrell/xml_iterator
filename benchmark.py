#!/usr/bin/env python
"""Synthetic benchmarks: dict parity + stream backends.

Single pipeline: measure once → print tables → write JSON → print README md.
No re-runs, no optional backends left out of results.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from xml_iterator.xml_iterator import iter_xml

from bench_common import (
    create_catalog_xml,
    drain_streams,
    json_stream_block,
    md_dict_table,
    md_stream_table,
    merge_results,
    print_dict_table,
    print_readme_block,
    print_stream_table,
    require_bench_deps,
    time_dict_pair,
    time_mean,
    ts,
)

# Full matrix for JSON; README subset below
DICT_SIZES = [100, 500, 1000, 2000, 5000]
README_DICT_SIZES = {500, 2000, 5000}
STREAM_ITEMS = 2000
EARLY_EXIT_EVENTS = 1000
EARLY_EXIT_ITEMS = 10000


def bench_dict_sizes(sizes: List[int], num_runs: int = 5) -> List[Dict[str, Any]]:
    rows = []
    for n in sizes:
        path = create_catalog_xml(n)
        try:
            pair = time_dict_pair(path, num_runs=num_runs)
            rows.append({"n": n, **pair})
        finally:
            os.unlink(path)
    return rows


def bench_stream_drain(num_items: int) -> Dict[str, Any]:
    path = create_catalog_xml(num_items)
    try:
        backends = drain_streams(path, max_events=None)
        return {
            "num_items": num_items,
            "file_size_mb": os.path.getsize(path) / (1024 * 1024),
            "backends": backends,
        }
    finally:
        os.unlink(path)


def bench_early_exit(num_items: int, max_events: int) -> Dict[str, Any]:
    """Early stream stop vs full dict — property of any streamer, not unique magic."""
    from xml_iterator.core import xml_to_dict

    path = create_catalog_xml(num_items)

    def early():
        n = 0
        for _ in iter_xml(path):
            n += 1
            if n >= max_events:
                break
        return n

    try:
        stream_s = time_mean(early, num_runs=5)
        dict_s = time_mean(xml_to_dict, path, num_runs=3)
        return {
            "num_items": num_items,
            "max_events": max_events,
            "file_size_mb": os.path.getsize(path) / (1024 * 1024),
            "stream_early_seconds": stream_s,
            "xml_to_dict_seconds": dict_s,
            "ratio_dict_over_early": (dict_s / stream_s) if stream_s > 0 else None,
        }
    finally:
        os.unlink(path)


def to_json_payload(
    dict_rows: List[Dict[str, Any]],
    stream: Dict[str, Any],
    early: Dict[str, Any],
) -> Dict[str, Any]:
    stamp = ts()
    out: Dict[str, Any] = {}
    for r in dict_rows:
        out[f"Synthetic_{r['n']}"] = {
            "kind": "synthetic_dict",
            "dataset": f"Synthetic ({r['n']} elements)",
            "n": r["n"],
            "file_size_mb": round(r["file_size_mb"], 4),
            "timestamp": stamp,
            "xml_iterator_full_seconds": round(r["xml_iterator_seconds"], 4),
            "xmltodict_full_seconds": round(r["xmltodict_seconds"], 4),
            "speedup_factor": round(r["speedup"], 2) if r["speedup"] else None,
        }
    out["Synthetic_stream_comparators"] = {
        "kind": "synthetic_stream",
        "dataset": f"Synthetic stream drain ({stream['num_items']} books)",
        "num_items": stream["num_items"],
        "file_size_mb": round(stream["file_size_mb"], 4),
        "timestamp": stamp,
        "backends": json_stream_block(stream["backends"]),
    }
    out["Synthetic_early_exit"] = {
        "kind": "synthetic_early_exit",
        "dataset": f"Early exit {early['max_events']} events vs full dict ({early['num_items']} items)",
        "num_items": early["num_items"],
        "max_events": early["max_events"],
        "file_size_mb": round(early["file_size_mb"], 4),
        "timestamp": stamp,
        "stream_early_seconds": round(early["stream_early_seconds"], 6),
        "xml_to_dict_seconds": round(early["xml_to_dict_seconds"], 4),
        "ratio_dict_over_early": round(early["ratio_dict_over_early"], 1) if early["ratio_dict_over_early"] else None,
    }
    return out


def main() -> None:
    require_bench_deps()

    print("xml_iterator synthetic benchmarks")
    print("=" * 60)

    print("\n[1/3] xml_to_dict vs xmltodict")
    dict_rows = bench_dict_sizes(DICT_SIZES, num_runs=5)
    print_dict_table(dict_rows)
    avg = sum(r["speedup"] for r in dict_rows) / len(dict_rows)
    print(f"average speedup: {avg:.2f}x")

    print("\n[2/3] stream backends (full drain)")
    stream = bench_stream_drain(STREAM_ITEMS)
    print_stream_table(
        f"synthetic {STREAM_ITEMS} books, full drain, {stream['file_size_mb']:.2f} MB",
        stream["backends"],
    )

    print("\n[3/3] early stream exit vs full dict")
    early = bench_early_exit(EARLY_EXIT_ITEMS, EARLY_EXIT_EVENTS)
    print(
        f"  {early['num_items']} items ({early['file_size_mb']:.2f} MB)\n"
        f"  stream first {early['max_events']} events: {early['stream_early_seconds']:.4f}s\n"
        f"  xml_to_dict full:                {early['xml_to_dict_seconds']:.4f}s\n"
        f"  ratio (any streamer gets this):  {early['ratio_dict_over_early']:.1f}x"
    )

    path = merge_results(to_json_payload(dict_rows, stream, early))
    print(f"\nsaved → {path}")

    readme_dict = [r for r in dict_rows if r["n"] in README_DICT_SIZES]
    print_readme_block("xml_to_dict vs xmltodict", md_dict_table(readme_dict))
    print_readme_block(
        f"stream backends ({STREAM_ITEMS} books, full drain)",
        md_stream_table(stream["backends"]),
    )


if __name__ == "__main__":
    main()
