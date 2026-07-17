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
# Full multi-backend drain of huge files is slow; early-exit always runs
FULL_STREAM_DRAIN_MAX_MB = 150.0

# Early-exit cap: must be large enough that wall time >> open/startup noise.
# 10k was ~3–10ms (useless). 1M is ~0.3s+ on SwissProt at ~3M ev/s.
EARLY_EXIT_EVENTS = 1_000_000


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

    Tasks:
      max_events=None → full drain (SAX *can*; skip only if file > SAX_FULL_DRAIN_MAX_MB — RAM)
      max_events=N    → early exit (SAX N/A with our adapter: materializes full parse first)

    Always includes every backend key; ineligible → skipped=…, never omitted.
    """
    if file_mb is None:
        file_mb = os.path.getsize(path) / (1024 * 1024)
    backends = available_stream_iterators()
    out: Dict[str, Dict[str, Any]] = {}
    for name, fn in backends.items():
        if name == "sax" and max_events is not None:
            out[name] = {"skipped": "N/A early-exit (SAX adapter materializes full parse first)"}
            continue
        if name == "sax" and max_events is None and file_mb > SAX_FULL_DRAIN_MAX_MB:
            # Valid task; skip for safety (list holds all events), not "can't do it"
            out[name] = {
                "skipped": (f"skipped full drain >{SAX_FULL_DRAIN_MAX_MB:.0f}MB (adapter buffers all events; RAM)")
            }
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


# ---------------------------------------------------------------------------
# README auto-sync (source of truth = benchmark_results.json)
# ---------------------------------------------------------------------------

README_PATH = Path("README.md")
BENCH_BEGIN = "<!-- BEGIN BENCHMARKS -->"
BENCH_END = "<!-- END BENCHMARKS -->"


def _fmt_s(sec: Optional[float], digits: int = 3) -> str:
    if sec is None:
        return "—"
    if sec < 0.001:
        return f"{sec:.4f}s"
    if sec < 1:
        return f"{sec:.3f}s"
    return f"{sec:.{digits}f}s"


def _fmt_mb(mb: float) -> str:
    if mb < 10:
        return f"{mb:.1f} MB"
    return f"{mb:.0f} MB"


def _fmt_rate(ev_s: Optional[float]) -> str:
    if not ev_s:
        return "—"
    if ev_s >= 1_000_000:
        return f"{ev_s / 1_000_000:.1f}M/s"
    if ev_s >= 1_000:
        return f"{ev_s / 1_000:.0f}k/s"
    return f"{ev_s:.0f}/s"


def _fmt_rel(rel: Optional[float]) -> str:
    if rel is None:
        return "—"
    if abs(rel - 1.0) < 0.05:
        return "1.00×"
    if rel > 1:
        return f"{rel:.2f}× slower"
    return f"{1 / rel:.2f}× faster"


def _stream_md_rows(backends: Dict[str, Any], order: Optional[List[str]] = None) -> str:
    names = order or list(backends.keys())
    # Prefer fastest-first among timed backends, keep declared order if given
    lines = [
        "| Backend | Time | Events | Rate | vs `xml_iterator` |",
        "|---------|------|--------|------|-------------------|",
    ]
    for name in names:
        if name not in backends:
            continue
        row = backends[name]
        if not row:
            continue
        if row.get("skipped") and "seconds" not in row:
            lines.append(f"| `{name}` | skipped | — | — | {row['skipped']} |")
            continue
        if "error" in row:
            lines.append(f"| `{name}` | error | — | — | {row['error']} |")
            continue
        lines.append(
            f"| `{name}` | {_fmt_s(row.get('seconds'))} | {row.get('events', 0):,} | "
            f"{_fmt_rate(row.get('events_per_sec'))} | {_fmt_rel(row.get('relative_to_xml_iterator'))} |"
        )
    return "\n".join(lines)


def _backend_order(backends: Dict[str, Any]) -> List[str]:
    """xml_iterator first, then others by ascending time, skipped last."""
    timed = []
    skipped = []
    for name, row in backends.items():
        if row and "seconds" in row:
            timed.append((row["seconds"], name))
        else:
            skipped.append(name)
    timed.sort()
    names = [n for _, n in timed]
    if "xml_iterator" in names:
        names.remove("xml_iterator")
        names = ["xml_iterator"] + names
    return names + skipped


def render_benchmarks_section(data: Optional[Dict[str, Any]] = None) -> str:
    """Markdown body for the README Benchmarks section (no H2 title)."""
    data = data if data is not None else load_results()
    if not data:
        return "No results yet. Run `make benchmark` and/or `make benchmark-all`, then `make readme-benchmarks`.\n"

    # timestamps
    stamps = [v.get("timestamp") for v in data.values() if isinstance(v, dict) and v.get("timestamp")]
    stamp = max(stamps) if stamps else "unknown"

    lines: List[str] = [
        "Release builds only (`make develop` / `make build`). Debug extensions are ~9× slower.",
        "",
        f"Numbers: **{stamp.split()[0] if stamp else 'unknown'}**, machine `bleepblop`. "
        f"Source of truth: [`benchmark_data/benchmark_results.json`](benchmark_data/benchmark_results.json) "
        f"(regenerate this section with `make readme-benchmarks`). "
        f"Narrative: [`PERF_2026-07-17.md`](PERF_2026-07-17.md).",
        "",
        "### Full-document dict — `xml_to_dict` vs `xmltodict.parse`",
        "",
        "Same output shape on synthetic / SwissProt (attributes included; namespace prefixes stripped). "
        "Full-file tree build — fine for modest docs / parity; streaming is the large-file path.",
        "",
    ]

    # synthetic dict rows
    synth = []
    for k, v in data.items():
        if isinstance(v, dict) and v.get("kind") == "synthetic_dict":
            synth.append(v)
    synth.sort(key=lambda r: r.get("n") or 0)
    if synth:
        lines += [
            "**Synthetic**",
            "",
            "| Elements | Size | `xml_iterator` | `xmltodict` | Speedup |",
            "|----------|------|----------------|-------------|---------|",
        ]
        preferred = [r for r in synth if r.get("n") in (500, 2000, 5000)]
        use = preferred if preferred else synth
        for r in use:
            lines.append(
                f"| {r['n']:,} | {_fmt_mb(r['file_size_mb'])} | "
                f"{_fmt_s(r['xml_iterator_full_seconds'])} | "
                f"{_fmt_s(r['xmltodict_full_seconds'])} | "
                f"{r['speedup_factor']:.1f}× |"
            )
        lines.append("")

    # real-world dict
    lines += [
        "**Real files**",
        "",
        "| Dataset | Size | `xml_iterator` | `xmltodict` | Speedup | Notes |",
        "|---------|------|----------------|-------------|---------|-------|",
    ]
    for key in ("SwissProt", "ESMA FIRDS"):
        r = data.get(key)
        if not isinstance(r, dict) or r.get("xml_iterator_full_seconds") is None:
            continue
        note = ""
        if r.get("results_identical") is True:
            note = "results identical"
        elif r.get("results_identical") is False:
            note = "results differ (shape)"
        sp = r.get("speedup_factor")
        sp_s = f"{sp:.2f}×" if sp is not None else "—"
        lines.append(
            f"| {r.get('dataset', key)} | {_fmt_mb(r['file_size_mb'])} | "
            f"{_fmt_s(r['xml_iterator_full_seconds'])} | "
            f"{_fmt_s(r.get('xmltodict_full_seconds'))} | {sp_s} | {note} |"
        )
    lines.append("")

    early = data.get("Synthetic_early_exit")
    if isinstance(early, dict):
        lines += [
            f"Early stream exit (stop after {early.get('max_events', 1000):,} events on a "
            f"{early.get('num_items', 0):,}-item file): "
            f"**{_fmt_s(early.get('stream_early_seconds'), 4)}** vs full `xml_to_dict` "
            f"**{_fmt_s(early.get('xml_to_dict_seconds'))}** "
            f"(~{early.get('ratio_dict_over_early', 0):.0f}×). "
            f"Any streaming parser gets this; not unique to this library.",
            "",
        ]

    lines += [
        "### Stream backends — same event profile",
        "",
        "Comparators in `xml_iterator.comparators`: `xml_iterator`, `et_iterparse`, `sax`, "
        "`lxml_iterparse`. All yield `(count, event, value)`. "
        "`make benchmark` / `make benchmark-all` time **every** backend (or record an explicit skip).",
        "",
        "**Policy (one stream table per file):** "
        f"full multi-backend drain if size ≤{FULL_STREAM_DRAIN_MAX_MB:.0f} MB (e.g. SwissProt); "
        f"else early exit first {EARLY_EXIT_EVENTS:,} events only (e.g. FIRDS). "
        "No redundant early+full on the same file. "
        "SAX is **N/A for early exit** (adapter materializes full parse first). "
        "SAX full drain skipped above 20 MB (RAM), not a capability gap.",
        "",
    ]

    stream = data.get("Synthetic_stream_comparators")
    if isinstance(stream, dict) and stream.get("backends"):
        b = stream["backends"]
        lines += [
            f"**Synthetic** — {stream.get('num_items', 0):,} books, full drain "
            f"({_fmt_mb(stream.get('file_size_mb', 0))}, "
            f"{next(iter(b.values())).get('events', 0):,} events)",
            "",
            _stream_md_rows(b, _backend_order(b)),
            "",
        ]

    # Prefer full drain when present (SwissProt); early only when that's all we have (FIRDS).
    # Do not show both for one dataset.
    for key in ("SwissProt", "ESMA FIRDS"):
        r = data.get(key)
        if not isinstance(r, dict):
            continue
        label = r.get("dataset", key)
        size = _fmt_mb(r.get("file_size_mb", 0))
        full = r.get("stream_comparators_full")
        early = r.get("stream_comparators_early") or r.get("stream_comparators_10k")
        if full:
            xi = full.get("xml_iterator") or {}
            lines += [
                f"**{label}** — full drain ({size}, {xi.get('events', 0):,} events)",
                "",
                _stream_md_rows(full, _backend_order(full)),
                "",
            ]
        elif early:
            n_ev = r.get("early_exit_events") or (early.get("xml_iterator") or {}).get("events")
            n_s = f"{n_ev:,}" if isinstance(n_ev, int) else "?"
            lines += [
                f"**{label}** — early exit first {n_s} events ({size}; "
                f"full multi-backend drain >{FULL_STREAM_DRAIN_MAX_MB:.0f} MB skipped)",
                "",
                _stream_md_rows(early, _backend_order(early)),
                "",
            ]

    lines += [
        "### Reproduce",
        "",
        "```bash",
        "make benchmark          # synthetic dict + stream + early-exit → JSON",
        "make benchmark-all      # SwissProt + FIRDS → JSON",
        "make show-benchmarks    # pretty-print last JSON (no rebuild)",
        "make readme-benchmarks  # rewrite this section from JSON (no re-run)",
        "```",
        "",
        "Makefile installs `.[bench]` (`xmltodict`, `lxml`) and a **release** extension first. "
        "Committed snapshot: [`benchmark_data/benchmark_results.json`](benchmark_data/benchmark_results.json).",
    ]
    return "\n".join(lines) + "\n"


def update_readme_benchmarks(readme_path: Path = README_PATH) -> Path:
    """Replace <!-- BEGIN/END BENCHMARKS --> block in README from JSON."""
    body = render_benchmarks_section()
    block = f"{BENCH_BEGIN}\n{body.rstrip()}\n{BENCH_END}"
    text = readme_path.read_text(encoding="utf-8")
    if BENCH_BEGIN in text and BENCH_END in text:
        pre, rest = text.split(BENCH_BEGIN, 1)
        _, post = rest.split(BENCH_END, 1)
        new = pre + block + post
    else:
        # Insert after "## Benchmarks\n"
        needle = "## Benchmarks\n"
        if needle not in text:
            raise SystemExit("README has no ## Benchmarks section and no markers")
        pre, post = text.split(needle, 1)
        # drop old content until next ##
        if "\n## " in post:
            old, after = post.split("\n## ", 1)
            new = pre + needle + "\n" + block + "\n\n## " + after
        else:
            new = pre + needle + "\n" + block + post
    readme_path.write_text(new, encoding="utf-8")
    return readme_path
