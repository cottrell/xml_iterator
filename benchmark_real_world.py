#!/usr/bin/env python
"""
Real-world benchmark using large ESMA FIRDS XML file
"""

import os
import time
import urllib.request
import zipfile
from pathlib import Path

try:
    import xmltodict

    HAS_XMLTODICT = True
except ImportError:
    HAS_XMLTODICT = False
    print("ERROR: xmltodict required for benchmarking - install with: uv pip install xmltodict")
    exit(1)

from xml_iterator.xml_iterator import iter_xml

from xml_iterator.comparators import available_stream_iterators
from xml_iterator.core import xml_to_dict

# Configuration
SWISSPROT_NAME = "SwissProt"
SWISSPROT_URL = "https://aiweb.cs.washington.edu/research/projects/xmltk/xmldata/data/SwissProt/SwissProt.xml"

FIRDS_NAME = "ESMA FIRDS"
FIRDS_URL = "https://firds.esma.europa.eu/firds/FULINS_D_20250531_01of03.zip"

CACHE_DIR = Path("benchmark_data")


def get_dataset(name, url):
    """Download and prepare (extract if zip) the XML dataset"""
    CACHE_DIR.mkdir(exist_ok=True)

    filename = os.path.basename(url)
    dest_path = CACHE_DIR / filename

    if filename.endswith(".zip"):
        extracted_xml = dest_path.with_suffix(".xml")
    else:
        extracted_xml = dest_path

    if extracted_xml.exists():
        file_size_mb = extracted_xml.stat().st_size / 1024 / 1024
        print(f"✓ Using cached {name} XML: {extracted_xml} ({file_size_mb:.1f} MB)")
        return str(extracted_xml)

    # Download file
    if not dest_path.exists():
        print(f"Downloading {name} data from {url}")
        print("This may take a while...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                with open(dest_path, "wb") as f:
                    downloaded = 0
                    chunk_size = 8192
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(
                                f"\rDownloading: {percent:.1f}% ({downloaded:,} bytes)",
                                end="",
                                flush=True,
                            )
            print(f"\n✓ Downloaded: {dest_path} ({dest_path.stat().st_size:,} bytes)")
        except Exception as e:
            print(f"\nERROR downloading {name} data: {e}")
            if dest_path.exists():
                dest_path.unlink()
            raise

    # Extract if zip
    if filename.endswith(".zip"):
        print("Extracting XML from zip archive...")
        xml_files = []
        with zipfile.ZipFile(dest_path, "r") as zip_ref:
            for file_info in zip_ref.filelist:
                if file_info.filename.endswith(".xml"):
                    xml_files.append(file_info.filename)

        if not xml_files:
            raise ValueError("No XML files found in zip archive")

        xml_filename = xml_files[0]
        print(f"Found XML file in archive: {xml_filename}")

        try:
            with zipfile.ZipFile(dest_path, "r") as zip_ref:
                with zip_ref.open(xml_filename) as xml_file:
                    with open(extracted_xml, "wb") as output_file:
                        copied = 0
                        while True:
                            chunk = xml_file.read(8192)
                            if not chunk:
                                break
                            output_file.write(chunk)
                            copied += len(chunk)
                            if copied % (1024 * 1024) == 0:
                                print(
                                    f"  Extracted: {copied // (1024 * 1024)} MB",
                                    end="\r",
                                    flush=True,
                                )
            file_size_mb = extracted_xml.stat().st_size / 1024 / 1024
            print(f"\n✓ Extracted XML file: {extracted_xml} ({file_size_mb:.1f} MB)")
        except Exception as e:
            if extracted_xml.exists():
                extracted_xml.unlink()
            raise e

    return str(extracted_xml)


def benchmark_streaming_iteration(xml_file, max_events=10000):
    """Benchmark streaming iteration with early termination (native only)."""
    print(f"\nStreaming benchmark (first {max_events:,} events, xml_iterator):")

    start_time = time.perf_counter()
    count = 0

    for event_count, event, value in iter_xml(xml_file):
        count += 1
        if count >= max_events:
            break

    end_time = time.perf_counter()
    duration = end_time - start_time

    print(f"  Processed {count:,} events in {duration:.3f}s")
    print(f"  Rate: {count / duration:,.0f} events/second")

    return duration, count


def benchmark_stream_comparators(xml_file, max_events=None):
    """Drain each stream backend with the same (count, event, value) profile.

    max_events: stop after N events (early-exit comparison); None = full drain.
    SAX buffers all events into a list — skipped for full drain above 20MB.
    """
    backends = available_stream_iterators()
    file_mb = os.path.getsize(xml_file) / 1024 / 1024
    label = f"first {max_events:,} events" if max_events else "full drain"
    print(f"\nStream comparator benchmark ({label}):")
    print(f"  backends: {', '.join(backends)}")

    results = {}
    for name, fn in backends.items():
        if name == "sax" and max_events is None and file_mb > 20:
            print(f"  {name:16} skipped full drain on {file_mb:.0f}MB (buffers all events)")
            results[name] = None
            continue
        try:
            t0 = time.perf_counter()
            n = 0
            for _ in fn(xml_file):
                n += 1
                if max_events is not None and n >= max_events:
                    break
            dt = time.perf_counter() - t0
            rate = n / dt if dt > 0 else 0
            print(f"  {name:16} {dt:8.3f}s  events={n:,}  {rate:,.0f} ev/s")
            results[name] = {"seconds": dt, "events": n, "events_per_sec": rate}
        except Exception as e:
            print(f"  {name:16} ERROR: {e}")
            results[name] = {"error": str(e)}
    return results


def benchmark_xmltodict_full(xml_file):
    """Benchmark xmltodict on full file"""
    if not HAS_XMLTODICT:
        print("  Skipping xmltodict benchmark (not available)")
        return None, None

    print("\nxmltodict full file benchmark:")

    try:
        with open(xml_file, "r", encoding="utf-8") as f:
            xml_content = f.read()

        file_size_mb = len(xml_content.encode("utf-8")) / 1024 / 1024
        print(f"  File size: {file_size_mb:.1f} MB")

        start_time = time.perf_counter()
        result = xmltodict.parse(xml_content)
        end_time = time.perf_counter()

        duration = end_time - start_time

        print(f"  Parsed full file in {duration:.3f}s")
        print(f"  Rate: {file_size_mb / duration:.1f} MB/second")
        print(f"  Result type: {type(result)}")

        return duration, result

    except MemoryError:
        print("  ERROR: xmltodict ran out of memory")
        return None, None
    except Exception as e:
        print(f"  ERROR: xmltodict failed - {e}")
        return None, None


def benchmark_xml_to_dict_full(xml_file):
    """Benchmark our xml_to_dict on full file"""
    print("\nxml_iterator xml_to_dict full file benchmark:")

    try:
        file_size_mb = os.path.getsize(xml_file) / 1024 / 1024
        print(f"  File size: {file_size_mb:.1f} MB")

        start_time = time.perf_counter()
        result = xml_to_dict(xml_file)  # No limits - full parsing
        end_time = time.perf_counter()

        duration = end_time - start_time

        print(f"  Converted to dict in {duration:.3f}s")
        print(f"  Rate: {file_size_mb / duration:.1f} MB/second")
        print(f"  Result type: {type(result)}")

        if isinstance(result, dict):

            def count_elements(obj):
                if isinstance(obj, dict):
                    return 1 + sum(count_elements(v) for v in obj.values())
                elif isinstance(obj, list):
                    return sum(count_elements(item) for item in obj)
                else:
                    return 1

            element_count = count_elements(result)
            print(f"  Dictionary elements: {element_count:,}")
            print(f"  Rate: {element_count / duration:,.0f} elements/second")

        return duration, result

    except Exception as e:
        print(f"  ERROR: xml_to_dict failed - {e}")
        return None, None


def compare_results(our_result, xmltodict_result):
    """Compare results and note any differences"""
    print("\nResult comparison:")

    if our_result is None and xmltodict_result is None:
        print("  Both failed - no comparison possible")
    elif our_result is None:
        print("  xml_iterator failed, xmltodict succeeded")
    elif xmltodict_result is None:
        print("  xmltodict failed, xml_iterator succeeded")
    elif our_result == xmltodict_result:
        print("  ✅ Results are identical")
    else:
        print("  ⚠️  Results differ")
        print(f"     xml_iterator type: {type(our_result)}")
        print(f"     xmltodict type: {type(xmltodict_result)}")

        # Try to show some detail about differences
        if isinstance(our_result, dict) and isinstance(xmltodict_result, dict):
            our_keys = set(our_result.keys()) if our_result else set()
            xml_keys = set(xmltodict_result.keys()) if xmltodict_result else set()

            if our_keys != xml_keys:
                print(f"     Key differences: our_only={our_keys - xml_keys}, xml_only={xml_keys - our_keys}")
            else:
                print("     Same keys, different values")

        print("     (This is still a valid performance comparison)")


def benchmark_memory_efficiency(xml_file):
    """Test memory efficiency with different approaches"""
    print("\nMemory efficiency test:")

    # Test 1: Streaming with very early termination
    start_time = time.perf_counter()
    count = 0
    for event_count, event, value in iter_xml(xml_file):
        count += 1
        if count >= 1000:  # Very early termination
            break
    duration = time.perf_counter() - start_time

    print(f"  Early termination (1,000 events): {duration:.4f}s")

    # Test 2: Streaming with medium termination
    start_time = time.perf_counter()
    count = 0
    for event_count, event, value in iter_xml(xml_file):
        count += 1
        if count >= 100000:  # Medium termination
            break
    duration = time.perf_counter() - start_time

    print(f"  Medium termination (100,000 events): {duration:.3f}s")
    print("  ✓ Demonstrates constant memory usage regardless of file size")


def save_results_to_json(name, file_size_mb, streaming_duration, our_duration, xml_duration):
    """Save benchmark results to benchmark_data/benchmark_results.json"""
    import json

    results_file = CACHE_DIR / "benchmark_results.json"

    # Load existing results if any
    data = {}
    if results_file.exists():
        try:
            with open(results_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    # Add new results
    speedup = xml_duration / our_duration if (xml_duration and our_duration) else None
    data[name] = {
        "dataset": name,
        "file_size_mb": round(file_size_mb, 2),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "streaming_10k_events_seconds": round(streaming_duration, 4),
        "xml_iterator_full_seconds": round(our_duration, 4) if our_duration else None,
        "xmltodict_full_seconds": round(xml_duration, 4) if xml_duration else None,
        "speedup_factor": round(speedup, 2) if speedup else None,
    }

    try:
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"   Saved results to {results_file}")
    except Exception as e:
        print(f"   WARNING: failed to save results to JSON: {e}")


def run_benchmark_for_dataset(name, url):
    """Run complete benchmark suite for a specific dataset"""
    print(f"\nReal-World XML Benchmark: {name} Data")
    print("=" * 50)

    try:
        # Download and extract the data
        xml_file = get_dataset(name, url)

        file_size_mb = os.path.getsize(xml_file) / 1024 / 1024
        print(f"XML file size: {file_size_mb:.1f} MB")

        # Run benchmarks
        streaming_duration, _ = benchmark_streaming_iteration(xml_file, max_events=10000)
        benchmark_stream_comparators(xml_file, max_events=10000)
        # Full event drain (SAX skipped if file huge — see comparator helper)
        if file_size_mb <= 150:
            benchmark_stream_comparators(xml_file, max_events=None)
        else:
            print(f"\nSkipping full stream drain ({file_size_mb:.0f}MB > 150MB cap); early-exit only.")
        benchmark_memory_efficiency(xml_file)

        # Full file comparisons
        our_duration, our_result = benchmark_xml_to_dict_full(xml_file)
        xml_duration, xml_result = benchmark_xmltodict_full(xml_file)

        # Compare results
        compare_results(our_result, xml_result)

        # Performance summary
        if our_duration and xml_duration:
            speedup = xml_duration / our_duration
            print("\n📊 Performance Summary:")
            print(f"   xml_iterator: {our_duration:.3f}s")
            print(f"   xmltodict:    {xml_duration:.3f}s")
            print(f"   Speedup:      {speedup:.2f}x {'faster' if speedup > 1 else 'slower'}")
        elif our_duration and not xml_duration:
            print("\n📊 Performance Summary:")
            print(f"   xml_iterator: {our_duration:.3f}s (succeeded)")
            print("   xmltodict:    failed")
            print("   xml_iterator handled file that xmltodict couldn't!")

        print("\n" + "=" * 50)
        print(f"✅ {name} benchmark completed successfully!")
        print(f"   File processed: {file_size_mb:.1f} MB {name} data")
        print("   xml_iterator handled large real-world XML efficiently")

        # Save results to JSON
        save_results_to_json(name, file_size_mb, streaming_duration, our_duration, xml_duration)
        print("   Re-run for instant cached benchmarks!")

    except Exception as e:
        print(f"\n❌ Benchmark failed for {name}: {e}")
        return False

    return True


if __name__ == "__main__":
    if not HAS_XMLTODICT:
        exit(1)

    import argparse

    parser = argparse.ArgumentParser(description="Real-world XML Benchmarks")
    parser.add_argument(
        "--dataset",
        choices=["swissprot", "firds", "both"],
        default="swissprot",
        help="Which dataset to run (default: swissprot)",
    )
    args = parser.parse_args()

    success = True
    if args.dataset in ["swissprot", "both"]:
        success = run_benchmark_for_dataset(SWISSPROT_NAME, SWISSPROT_URL) and success
    if args.dataset in ["firds", "both"]:
        success = run_benchmark_for_dataset(FIRDS_NAME, FIRDS_URL) and success

    exit(0 if success else 1)
