#!/usr/bin/env python
"""
Benchmark script comparing xml_iterator.xml_to_dict vs xmltodict
"""

import os
import statistics
import tempfile
import time
from typing import Tuple

try:
    import xmltodict

    HAS_XMLTODICT = True
except ImportError:
    HAS_XMLTODICT = False
    print("ERROR: xmltodict required for benchmarking - install with: uv pip install xmltodict")
    exit(1)

from xml_iterator.comparators import available_stream_iterators
from xml_iterator.core import xml_to_dict


def create_test_xml(num_items: int) -> str:
    """Create XML file with specified number of items"""
    fd, path = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<catalog>\n')
            for i in range(num_items):
                f.write(f'''  <book id="{i}">
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
''')
            f.write("</catalog>\n")
        return path
    except:
        os.close(fd)
        raise


def time_function(func, *args, num_runs: int = 5) -> Tuple[float, float]:
    """Time function execution with multiple runs"""
    times = []
    for _ in range(num_runs):
        start = time.perf_counter()
        _ = func(*args)
        end = time.perf_counter()
        times.append(end - start)

    return statistics.mean(times), statistics.stdev(times) if len(times) > 1 else 0.0


def benchmark_xmltodict_compatibility():
    """Benchmark xml_to_dict vs xmltodict on various file sizes"""
    print("XML Parser Benchmark: xml_iterator vs xmltodict")
    print("=" * 60)
    print()

    test_sizes = [100, 500, 1000, 2000, 5000]
    results = []

    for size in test_sizes:
        print(f"Testing with {size} XML elements...")
        xml_file = create_test_xml(size)
        file_size_mb = os.path.getsize(xml_file) / 1024 / 1024

        try:
            # Benchmark our implementation
            our_mean, our_std = time_function(xml_to_dict, xml_file, num_runs=5)

            # Benchmark xmltodict
            def xmltodict_parse(filepath):
                with open(filepath, "r") as f:
                    return xmltodict.parse(f.read())

            xml_mean, xml_std = time_function(xmltodict_parse, xml_file, num_runs=5)

            # Calculate speedup
            speedup = xml_mean / our_mean if our_mean > 0 else float("inf")

            results.append(
                {
                    "size": size,
                    "file_size_mb": file_size_mb,
                    "our_time": our_mean,
                    "our_std": our_std,
                    "xml_time": xml_mean,
                    "xml_std": xml_std,
                    "speedup": speedup,
                }
            )

        finally:
            os.unlink(xml_file)

    # Print results table
    print()
    print("Benchmark Results:")
    print("-" * 80)
    print(f"{'Elements':<8} {'File Size':<10} {'xml_iterator':<15} {'xmltodict':<15} {'Speedup':<10}")
    print(f"{'':8} {'(MB)':<10} {'(seconds)':<15} {'(seconds)':<15} {'(x)':<10}")
    print("-" * 80)

    for r in results:
        size = r["size"]
        file_mb = r["file_size_mb"]
        our_t = r["our_time"]
        xml_t = r["xml_time"]
        speedup = r["speedup"]
        print(f"{size:<8} {file_mb:<10.2f} {our_t:<15.3f} {xml_t:<15.3f} {speedup:<10.2f}")

    print("-" * 80)

    # Summary statistics
    avg_speedup = statistics.mean([r["speedup"] for r in results])
    print("\nSummary:")
    print(f"Average speedup: {avg_speedup:.2f}x")

    if avg_speedup > 1.0:
        print(f"✅ xml_iterator is {avg_speedup:.1f}x faster than xmltodict on average")
    else:
        print(f"⚠️  xml_iterator is {1 / avg_speedup:.1f}x slower than xmltodict on average")

    return results


def benchmark_streaming_vs_dict():
    """Compare streaming iteration vs full dict conversion"""
    print("\n" + "=" * 60)
    print("Streaming vs Dictionary Conversion Benchmark")
    print("=" * 60)

    size = 10000
    xml_file = create_test_xml(size)

    try:
        # Time streaming (early termination)
        def stream_early_exit(filepath, max_events=1000):
            from xml_iterator.xml_iterator import iter_xml

            count = 0
            for event_count, event, value in iter_xml(filepath):
                count += 1
                if count >= max_events:
                    break
            return count

        stream_time, _ = time_function(stream_early_exit, xml_file, 1000)

        # Time full dict conversion
        dict_time, _ = time_function(xml_to_dict, xml_file)

        print(f"File size: {size} elements ({os.path.getsize(xml_file) / 1024:.1f} KB)")
        print(f"Streaming (1000 events): {stream_time:.4f}s")
        print(f"Full dict conversion:    {dict_time:.4f}s")
        print(f"Streaming advantage:     {dict_time / stream_time:.1f}x faster for early termination")

    finally:
        os.unlink(xml_file)


def save_synthetic_results(results):
    """Save synthetic benchmark results to benchmark_data/benchmark_results.json"""
    import json
    from pathlib import Path

    results_dir = Path("benchmark_data")
    results_dir.mkdir(exist_ok=True)
    results_file = results_dir / "benchmark_results.json"

    data = {}
    if results_file.exists():
        try:
            with open(results_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    for size, file_mb, our_time, xml_time, speedup in results:
        key = f"Synthetic_{size}"
        data[key] = {
            "dataset": f"Synthetic ({size} elements)",
            "file_size_mb": round(file_mb, 4),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "xml_iterator_full_seconds": round(our_time, 4),
            "xmltodict_full_seconds": round(xml_time, 4),
            "speedup_factor": round(speedup, 2),
        }

    try:
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"\n✓ Saved synthetic results to {results_file}")
    except Exception as e:
        print(f"\nWARNING: failed to save synthetic results to JSON: {e}")


def generate_readme_table():
    """Generate benchmark table for README"""
    print("\n" + "=" * 60)
    print("README Table Format")
    print("=" * 60)

    results = []
    test_sizes = [500, 2000, 5000]

    for size in test_sizes:
        xml_file = create_test_xml(size)
        file_size_mb = os.path.getsize(xml_file) / 1024 / 1024

        try:
            our_mean, _ = time_function(xml_to_dict, xml_file, num_runs=3)

            def xmltodict_parse(filepath):
                with open(filepath, "r") as f:
                    return xmltodict.parse(f.read())

            xml_mean, _ = time_function(xmltodict_parse, xml_file, num_runs=3)
            speedup = xml_mean / our_mean if our_mean > 0 else float("inf")

            results.append((size, file_size_mb, our_mean, xml_mean, speedup))

        finally:
            os.unlink(xml_file)

    print("\nFor README.md:")
    print("```")
    print("| Elements | File Size | xml_iterator | xmltodict | Speedup |")
    print("|----------|-----------|--------------|-----------|---------|")
    for size, file_mb, our_time, xml_time, speedup in results:
        print(f"| {size:,} | {file_mb:.1f} MB | {our_time:.3f}s | {xml_time:.3f}s | {speedup:.1f}x |")
    print("```")

    save_synthetic_results(results)


def benchmark_stream_comparators_synthetic(num_items: int = 2000, max_events=None):
    """Full drain (or capped) of each stream backend on synthetic XML."""
    print("\n" + "=" * 60)
    print(f"Stream comparators (synthetic {num_items} books, max_events={max_events})")
    print("=" * 60)
    xml_file = create_test_xml(num_items)
    try:
        backends = available_stream_iterators()
        print(f"backends: {', '.join(backends)}")
        rows = []
        for name, fn in backends.items():
            t0 = time.perf_counter()
            n = 0
            for _ in fn(xml_file):
                n += 1
                if max_events is not None and n >= max_events:
                    break
            dt = time.perf_counter() - t0
            print(f"  {name:16} {dt:8.3f}s  events={n:,}  {n / dt:,.0f} ev/s")
            rows.append((name, dt, n))
        if rows:
            baseline = next((dt for name, dt, _ in rows if name == "xml_iterator"), rows[0][1])
            print("\n  relative to xml_iterator (lower time better):")
            for name, dt, n in rows:
                rel = dt / baseline if baseline > 0 else float("inf")
                print(f"    {name:16} {rel:.2f}x")
    finally:
        os.unlink(xml_file)


if __name__ == "__main__":
    if not HAS_XMLTODICT:
        exit(1)

    benchmark_xmltodict_compatibility()
    benchmark_streaming_vs_dict()
    benchmark_stream_comparators_synthetic(num_items=2000)
    generate_readme_table()
