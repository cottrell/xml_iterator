"""Shared benchmark helpers. One path for measure → print → JSON.

Every result that is printed must go through these helpers so nothing is
forgotten (stream backends, dict timings, markdown snippets).
"""

from __future__ import annotations

import json
import os
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import xmltodict

from xml_iterator.comparators import available_stream_iterators
from xml_iterator.core import xml_to_dict

CACHE_DIR = Path("benchmark_data")
RESULTS_PATH = CACHE_DIR / "benchmark_results.json"

# SAX materializes all events — skip full drain on large files
SAX_FULL_DRAIN_MAX_MB = 20.0
# Full multi-backend drain of huge files is slow; still run 10k early-exit always
FULL_STREAM_DRAIN_MAX_MB = 150.0


def require_bench_deps() -> None:
    """Fail fast with install hint. lxml is required for honest stream benches."""
    missing = []
    try:
        import xmltodict  # noqa: F401
    except ImportError:
        missing.append("xmltodict")
    try:
        import lxml.etree  # noqa: F401
    except ImportError:
        missing.append("lxml")
    if missing:
        raise SystemExit(f"Missing bench deps: {', '.join(missing)}\nInstall: uv pip install -e \".[bench]\"")
    backends = available_stream_iterators()
    for name in ("xml_iterator", "et_iterparse", "sax", "lxml_iterparse"):
        if name not in backends:
            raise SystemExit(f"Stream backend missing: {name} (got {list(backends)})")


def ts() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def time_mean(fn: Callable[..., Any], *args: Any, num_runs: int = 5) -> float:
    times = []
    for _ in range(num_runs):
        t0 = time.perf_counter()
        fn(*args)
        times.append(time.perf_counter() - t0)
    return statistics.mean(times)


def parse_xmltodict(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return xmltodict.parse(f.read())


def create_catalog_xml(num_items: int) -> str:
    fd, path = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<catalog>\n')
            for i in range(num_items):
                f.write(
                    f"""  <book id="{i}">
    <title>Book Title {i}</title>
    <author>Author {i % 100}</author>
    <year>{2000 + (i % 24)}</year>
    <price>${(i % 50) + 10}.99</price>
    <description>Description for book {i} with some longer text content to make parsing more realistic.</description>
    <categories>
      <category>Fiction</category>
      <category>Adventure</category>
    </categories>
  </book>
"""
                )
            f.write("</catalog>\n")
        return path
    except Exception:
        os.close(fd)
        raise


def _round_backend(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    if "error" in row:
        return {"error": row["error"], "skipped": row.get("skipped")}
    if "skipped" in row and "seconds" not in row:
        return {"skipped": row["skipped"]}
    out: Dict[str, Any] = {
        "seconds": round(row["seconds"], 4),
        "events": row["events"],
        "events_per_sec": round(row["events_per_sec"]) if row.get("events_per_sec") else 0,
    }
    if "relative_to_xml_iterator" in row and row["relative_to_xml_iterator"] is not None:
        out["relative_to_xml_iterator"] = round(row["relative_to_xml_iterator"], 2)
    if row.get("skipped"):
        out["skipped"] = row["skipped"]
    return out


def attach_relative(backends: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Add relative_to_xml_iterator on timed rows (mutates and returns)."""
    base = None
    if "xml_iterator" in backends and "seconds" in backends["xml_iterator"]:
        base = backends["xml_iterator"]["seconds"]
    for row in backends.values():
        if base and "seconds" in row and row["seconds"] > 0:
            row["relative_to_xml_iterator"] = row["seconds"] / base
        elif "seconds" in row:
            row["relative_to_xml_iterator"] = None
    return backends


def drain_streams(
    path: str,
    max_events: Optional[int] = None,
    *,
    file_mb: Optional[float] = None,
) -> Dict[str, Dict[str, Any]]:
    """Time every available stream backend. Returns name → result dict.

    Always includes every backend key. SAX full drain on large files is
    recorded as skipped (not omitted).
    """
    if file_mb is None:
        file_mb = os.path.getsize(path) / (1024 * 1024)
    backends = available_stream_iterators()
    out: Dict[str, Dict[str, Any]] = {}
    for name, fn in backends.items():
        if name == "sax" and max_events is None and file_mb > SAX_FULL_DRAIN_MAX_MB:
            out[name] = {"skipped": f"full drain >{SAX_FULL_DRAIN_MAX_MB:.0f}MB (SAX buffers all events)"}
            continue
        try:
            t0 = time.perf_counter()
            n = 0
            for _ in fn(path):
                n += 1
                if max_events is not None and n >= max_events:
                    break
            dt = time.perf_counter() - t0
            out[name] = {
                "seconds": dt,
                "events": n,
                "events_per_sec": (n / dt) if dt > 0 else 0.0,
            }
        except Exception as e:
            out[name] = {"error": str(e)}
    return attach_relative(out)


def time_dict_pair(path: str, num_runs: int = 5) -> Dict[str, Any]:
    """xml_to_dict vs xmltodict on one file."""
    our = time_mean(xml_to_dict, path, num_runs=num_runs)
    xt = time_mean(parse_xmltodict, path, num_runs=num_runs)
    return {
        "xml_iterator_seconds": our,
        "xmltodict_seconds": xt,
        "speedup": (xt / our) if our > 0 else None,
        "file_size_mb": os.path.getsize(path) / (1024 * 1024),
    }


def load_results() -> Dict[str, Any]:
    if not RESULTS_PATH.exists():
        return {}
    try:
        with open(RESULTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_results(data: Dict[str, Any]) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    tmp = RESULTS_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    tmp.replace(RESULTS_PATH)


def merge_results(updates: Dict[str, Any]) -> Path:
    """Merge top-level keys into results JSON (atomic write)."""
    data = load_results()
    data.update(updates)
    save_results(data)
    return RESULTS_PATH


def json_stream_block(backends: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return {name: _round_backend(row) for name, row in backends.items()}


def print_stream_table(title: str, backends: Dict[str, Dict[str, Any]]) -> None:
    print(f"\n{title}")
    print(f"{'backend':<16} {'seconds':>10} {'events':>12} {'ev/s':>12} {'vs xi':>8}")
    print("-" * 62)
    for name, row in backends.items():
        if row.get("skipped") and "seconds" not in row:
            print(f"{name:<16} {'skipped':>10}  {row['skipped']}")
            continue
        if "error" in row:
            print(f"{name:<16} ERROR: {row['error']}")
            continue
        rel = row.get("relative_to_xml_iterator")
        rel_s = f"{rel:.2f}x" if rel is not None else "-"
        print(f"{name:<16} {row['seconds']:10.4f} {row['events']:12,} {row['events_per_sec']:12,.0f} {rel_s:>8}")


def print_dict_table(rows: List[Dict[str, Any]]) -> None:
    print(f"\n{'n':>8} {'MB':>8} {'xml_iterator':>14} {'xmltodict':>12} {'speedup':>10}")
    print("-" * 58)
    for r in rows:
        print(
            f"{r['n']:>8} {r['file_size_mb']:8.2f} "
            f"{r['xml_iterator_seconds']:14.4f} {r['xmltodict_seconds']:12.4f} "
            f"{r['speedup']:9.2f}x"
        )


def md_dict_table(rows: List[Dict[str, Any]]) -> str:
    lines = [
        "| Elements | Size | `xml_iterator.xml_to_dict` | `xmltodict.parse` | Speedup |",
        "|----------|------|----------------------------|-------------------|---------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['n']:,} | {r['file_size_mb']:.1f} MB | "
            f"{r['xml_iterator_seconds']:.3f}s | {r['xmltodict_seconds']:.3f}s | "
            f"{r['speedup']:.1f}× |"
        )
    return "\n".join(lines)


def md_stream_table(backends: Dict[str, Dict[str, Any]]) -> str:
    lines = [
        "| Backend | Time | Events | Rate | vs `xml_iterator` |",
        "|---------|------|--------|------|-------------------|",
    ]
    for name, row in backends.items():
        if row.get("skipped") and "seconds" not in row:
            lines.append(f"| `{name}` | skipped | — | — | {row['skipped']} |")
            continue
        if "error" in row:
            lines.append(f"| `{name}` | error | — | — | {row['error']} |")
            continue
        rel = row.get("relative_to_xml_iterator")
        rel_s = f"{rel:.2f}×" if rel is not None else "—"
        slower = ""
        if rel is not None and rel > 1.05:
            slower = " slower"
        elif rel is not None and rel < 0.95:
            slower = " faster"
        lines.append(
            f"| `{name}` | {row['seconds']:.3f}s | {row['events']:,} | "
            f"{row['events_per_sec']:,.0f} ev/s | {rel_s}{slower} |"
        )
    return "\n".join(lines)


def print_readme_block(title: str, md: str) -> None:
    print(f"\n# README: {title}")
    print("```")
    print(md)
    print("```")
