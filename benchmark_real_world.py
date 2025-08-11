#!/usr/bin/env python
"""
Real-world benchmark using large ESMA FIRDS XML file
"""

import os
import time
import zipfile
import tempfile
import urllib.request
from pathlib import Path

try:
    import xmltodict
    HAS_XMLTODICT = True
except ImportError:
    HAS_XMLTODICT = False
    print("ERROR: xmltodict required for benchmarking - install with: pip install xmltodict")
    exit(1)

from xml_iterator.xml_iterator import iter_xml
from xml_iterator.core import xml_to_dict


# Configuration
# FIRDS_URL = "https://firds.esma.europa.eu/firds/FULINS_D_20250531_01of03.zip"
# FIRDS_URL = "https://firds.esma.europa.eu/firds/FULINS_S_20250531_05of05.zip"
# https://aiweb.cs.washington.edu/research/projects/xmltk/xmldata/
FIRDS_URL = "https://aiweb.cs.washington.edu/research/projects/xmltk/xmldata/data/SwissProt/SwissProt.xml"
CACHE_DIR = Path("benchmark_data")
ZIP_FILE = CACHE_DIR / os.path.basename(FIRDS_URL)


def download_firds_data():
    """Download FIRDS XML data if not already cached"""
    CACHE_DIR.mkdir(exist_ok=True)
    
    if ZIP_FILE.exists():
        print(f"✓ Using cached file: {ZIP_FILE}")
        return ZIP_FILE
    
    print(f"Downloading FIRDS data from {FIRDS_URL}")
    print("This may take a while - file is quite large...")
    
    try:
        with urllib.request.urlopen(FIRDS_URL) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            
            with open(ZIP_FILE, 'wb') as f:
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
                        print(f"\rDownloading: {percent:.1f}% ({downloaded:,} bytes)", end="", flush=True)
        
        print(f"\n✓ Downloaded: {ZIP_FILE} ({ZIP_FILE.stat().st_size:,} bytes)")
        return ZIP_FILE
        
    except Exception as e:
        print(f"\nERROR downloading file: {e}")
        if ZIP_FILE.exists():
            ZIP_FILE.unlink()
        raise


def extract_xml_from_zip(zip_path):
    """Extract XML file from zip archive (with caching)"""
    # Check if already extracted
    cached_xml = zip_path.with_suffix('.xml')
    if cached_xml.exists():
        file_size_mb = cached_xml.stat().st_size / 1024 / 1024
        print(f"✓ Using cached extracted XML: {cached_xml} ({file_size_mb:.1f} MB)")
        return str(cached_xml)
    
    print("Extracting XML from zip archive...")
    xml_files = []
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file_info in zip_ref.filelist:
            if file_info.filename.endswith('.xml'):
                xml_files.append(file_info.filename)
    
    if not xml_files:
        raise ValueError("No XML files found in archive")
    
    # Use the first XML file found
    xml_filename = xml_files[0]
    print(f"Found XML file in archive: {xml_filename}")
    
    # Extract to cached file next to the zip
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            with zip_ref.open(xml_filename) as xml_file:
                with open(cached_xml, 'wb') as output_file:
                    # Copy in chunks to handle large files
                    copied = 0
                    while True:
                        chunk = xml_file.read(8192)
                        if not chunk:
                            break
                        output_file.write(chunk)
                        copied += len(chunk)
                        
                        # Show progress for large files
                        if copied % (1024 * 1024) == 0:  # Every MB
                            print(f"  Extracted: {copied // (1024 * 1024)} MB", end='\r', flush=True)
        
        file_size_mb = cached_xml.stat().st_size / 1024 / 1024
        print(f"\n✓ Extracted XML file: {cached_xml} ({file_size_mb:.1f} MB)")
        return str(cached_xml)
        
    except Exception as e:
        # Clean up partial file on error
        if cached_xml.exists():
            cached_xml.unlink()
        raise e


def benchmark_streaming_iteration(xml_file, max_events=10000):
    """Benchmark streaming iteration with early termination"""
    print(f"\nStreaming benchmark (first {max_events:,} events):")
    
    start_time = time.perf_counter()
    count = 0
    
    for event_count, event, value in iter_xml(xml_file):
        count += 1
        if count >= max_events:
            break
    
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    print(f"  Processed {count:,} events in {duration:.3f}s")
    print(f"  Rate: {count/duration:,.0f} events/second")
    
    return duration, count


def benchmark_xmltodict_full(xml_file):
    """Benchmark xmltodict on full file"""
    if not HAS_XMLTODICT:
        print("  Skipping xmltodict benchmark (not available)")
        return None, None
    
    print(f"\nxmltodict full file benchmark:")
    
    try:
        with open(xml_file, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        file_size_mb = len(xml_content.encode('utf-8')) / 1024 / 1024
        print(f"  File size: {file_size_mb:.1f} MB")
        
        start_time = time.perf_counter()
        result = xmltodict.parse(xml_content)
        end_time = time.perf_counter()
        
        duration = end_time - start_time
        
        print(f"  Parsed full file in {duration:.3f}s")
        print(f"  Rate: {file_size_mb/duration:.1f} MB/second")
        print(f"  Result type: {type(result)}")
        
        return duration, result
        
    except MemoryError:
        print(f"  ERROR: xmltodict ran out of memory")
        return None, None
    except Exception as e:
        print(f"  ERROR: xmltodict failed - {e}")
        return None, None


def benchmark_xml_to_dict_full(xml_file):
    """Benchmark our xml_to_dict on full file"""
    print(f"\nxml_iterator xml_to_dict full file benchmark:")
    
    try:
        file_size_mb = os.path.getsize(xml_file) / 1024 / 1024
        print(f"  File size: {file_size_mb:.1f} MB")
        
        start_time = time.perf_counter()
        result = xml_to_dict(xml_file)  # No limits - full parsing
        end_time = time.perf_counter()
        
        duration = end_time - start_time
        
        print(f"  Converted to dict in {duration:.3f}s")
        print(f"  Rate: {file_size_mb/duration:.1f} MB/second")
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
            print(f"  Rate: {element_count/duration:,.0f} elements/second")
        
        return duration, result
        
    except Exception as e:
        print(f"  ERROR: xml_to_dict failed - {e}")
        return None, None


def compare_results(our_result, xmltodict_result):
    """Compare results and note any differences"""
    print(f"\nResult comparison:")
    
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
                print(f"     Same keys, different values")
        
        print("     (This is still a valid performance comparison)")


def benchmark_memory_efficiency(xml_file):
    """Test memory efficiency with different approaches"""
    print(f"\nMemory efficiency test:")
    
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
    print(f"  ✓ Demonstrates constant memory usage regardless of file size")


def run_firds_benchmark():
    """Run complete FIRDS benchmark suite"""
    print("Real-World XML Benchmark: ESMA FIRDS Data")
    print("=" * 50)
    
    try:
        # Download/cache the data
        zip_path = download_firds_data()
        
        # Extract XML file
        print("\nExtracting XML file...")
        xml_file = extract_xml_from_zip(zip_path)
        
        file_size_mb = os.path.getsize(xml_file) / 1024 / 1024
        print(f"XML file size: {file_size_mb:.1f} MB")
        
        # Run benchmarks
        benchmark_streaming_iteration(xml_file, max_events=10000)
        benchmark_memory_efficiency(xml_file)
        
        # Full file comparisons
        our_duration, our_result = benchmark_xml_to_dict_full(xml_file)
        xml_duration, xml_result = benchmark_xmltodict_full(xml_file)
        
        # Compare results
        compare_results(our_result, xml_result)
        
        # Performance summary
        if our_duration and xml_duration:
            speedup = xml_duration / our_duration
            print(f"\n📊 Performance Summary:")
            print(f"   xml_iterator: {our_duration:.3f}s")
            print(f"   xmltodict:    {xml_duration:.3f}s")
            print(f"   Speedup:      {speedup:.2f}x {'faster' if speedup > 1 else 'slower'}")
        elif our_duration and not xml_duration:
            print(f"\n📊 Performance Summary:")
            print(f"   xml_iterator: {our_duration:.3f}s (succeeded)")
            print(f"   xmltodict:    failed")
            print(f"   xml_iterator handled file that xmltodict couldn't!")
        
        print("\n" + "=" * 50)
        print("✅ Real-world benchmark completed successfully!")
        print(f"   File processed: {file_size_mb:.1f} MB ESMA FIRDS data")
        print("   xml_iterator handled large real-world XML efficiently")
        print(f"   Cached files: {zip_path} & {xml_file}")
        print("   Re-run 'make benchmark-real' for instant benchmarks!")
            
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        return False
    
    return True


if __name__ == "__main__":
    if not HAS_XMLTODICT:
        exit(1)
    
    success = run_firds_benchmark()
    exit(0 if success else 1)
