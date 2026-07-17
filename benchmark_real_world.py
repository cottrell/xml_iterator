#!/usr/bin/env python
"""Real-world benchmarks (SwissProt / ESMA FIRDS).

Same helpers as synthetic: every stream backend timed, everything saved to JSON.
"""

from __future__ import annotations

import argparse
import os
import time
import urllib.request
import zipfile
from typing import Any, Dict, Optional, Tuple

from bench_common import (
    CACHE_DIR,
    FULL_STREAM_DRAIN_MAX_MB,
    drain_streams,
    json_stream_block,
    merge_results,
    parse_xmltodict,
    print_stream_table,
    require_bench_deps,
    ts,
)
from xml_iterator.core import xml_to_dict

SWISSPROT = (
    "SwissProt",
    "https://aiweb.cs.washington.edu/research/projects/xmltk/xmldata/data/SwissProt/SwissProt.xml",
)
FIRDS = (
    "ESMA FIRDS",
    "https://firds.esma.europa.eu/firds/FULINS_D_20250531_01of03.zip",
)


def get_dataset(name: str, url: str) -> str:
    CACHE_DIR.mkdir(exist_ok=True)
    filename = os.path.basename(url)
    dest = CACHE_DIR / filename
    xml_path = dest.with_suffix(".xml") if filename.endswith(".zip") else dest

    if xml_path.exists():
        mb = xml_path.stat().st_size / (1024 * 1024)
        print(f"cached {name}: {xml_path} ({mb:.1f} MB)")
        return str(xml_path)

    if not dest.exists():
        print(f"downloading {name} …")
        req = urllib.request.Request(url, headers={"User-Agent": "xml_iterator-bench/0.2"})
        with urllib.request.urlopen(req) as resp, open(dest, "wb") as f:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        print(f"downloaded {dest} ({dest.stat().st_size:,} bytes)")

    if filename.endswith(".zip"):
        with zipfile.ZipFile(dest, "r") as zf:
            xml_names = [i.filename for i in zf.filelist if i.filename.endswith(".xml")]
            if not xml_names:
                raise ValueError("no XML in zip")
            with zf.open(xml_names[0]) as src, open(xml_path, "wb") as out:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
        print(f"extracted {xml_path} ({xml_path.stat().st_size / (1024 * 1024):.1f} MB)")

    return str(xml_path)


def time_full_dict(path: str) -> Tuple[Optional[float], Optional[Any], Optional[str]]:
    try:
        t0 = time.perf_counter()
        result = xml_to_dict(path)
        return time.perf_counter() - t0, result, None
    except Exception as e:
        return None, None, str(e)


def time_xmltodict(path: str) -> Tuple[Optional[float], Optional[Any], Optional[str]]:
    try:
        t0 = time.perf_counter()
        result = parse_xmltodict(path)
        return time.perf_counter() - t0, result, None
    except Exception as e:
        return None, None, str(e)


def run_dataset(name: str, url: str) -> bool:
    print(f"\n{'=' * 60}\n{name}\n{'=' * 60}")
    path = get_dataset(name, url)
    file_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"size: {file_mb:.1f} MB")

    # 1) early stream (all backends)
    stream_10k = drain_streams(path, max_events=10_000, file_mb=file_mb)
    print_stream_table("stream backends — first 10_000 events", stream_10k)

    # 2) full stream drain when cheap enough
    stream_full = None
    if file_mb <= FULL_STREAM_DRAIN_MAX_MB:
        stream_full = drain_streams(path, max_events=None, file_mb=file_mb)
        print_stream_table("stream backends — full drain", stream_full)
    else:
        print(f"\nfull stream drain skipped ({file_mb:.0f} MB > {FULL_STREAM_DRAIN_MAX_MB:.0f} MB cap)")

    # 3) full-file dict
    print("\nfull-file dict")
    our_s, our_r, our_err = time_full_dict(path)
    xt_s, xt_r, xt_err = time_xmltodict(path)
    if our_err:
        print(f"  xml_to_dict: ERROR {our_err}")
    else:
        print(f"  xml_to_dict: {our_s:.3f}s  ({file_mb / our_s:.1f} MB/s)")
    if xt_err:
        print(f"  xmltodict:   ERROR {xt_err}")
    else:
        print(f"  xmltodict:   {xt_s:.3f}s  ({file_mb / xt_s:.1f} MB/s)")
    if our_s and xt_s:
        print(f"  speedup:     {xt_s / our_s:.2f}x")
    if our_r is not None and xt_r is not None:
        print(f"  results identical: {our_r == xt_r}")

    xi_10k = stream_10k.get("xml_iterator", {})
    entry: Dict[str, Any] = {
        "kind": "real_world",
        "dataset": name,
        "file_size_mb": round(file_mb, 2),
        "timestamp": ts(),
        "streaming_10k_events_seconds": round(xi_10k["seconds"], 4) if "seconds" in xi_10k else None,
        "stream_comparators_10k": json_stream_block(stream_10k),
        "stream_comparators_full": json_stream_block(stream_full) if stream_full else None,
        "xml_iterator_full_seconds": round(our_s, 4) if our_s is not None else None,
        "xmltodict_full_seconds": round(xt_s, 4) if xt_s is not None else None,
        "speedup_factor": round(xt_s / our_s, 2) if (our_s and xt_s) else None,
        "results_identical": (our_r == xt_r) if (our_r is not None and xt_r is not None) else None,
        "errors": {k: v for k, v in {"xml_to_dict": our_err, "xmltodict": xt_err}.items() if v} or None,
    }
    out = merge_results({name: entry})
    print(f"\nsaved → {out}")
    return our_err is None


def main() -> None:
    require_bench_deps()
    parser = argparse.ArgumentParser(description="Real-world XML benchmarks")
    parser.add_argument(
        "--dataset",
        choices=["swissprot", "firds", "both"],
        default="swissprot",
    )
    args = parser.parse_args()

    ok = True
    if args.dataset in ("swissprot", "both"):
        ok = run_dataset(*SWISSPROT) and ok
    if args.dataset in ("firds", "both"):
        ok = run_dataset(*FIRDS) and ok

    from bench_common import update_readme_benchmarks

    rp = update_readme_benchmarks()
    print(f"\nREADME benchmarks section → {rp}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
