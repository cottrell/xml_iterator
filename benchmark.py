#!/usr/bin/env python
"""
Benchmark script comparing xml_iterator.xml_to_dict vs xmltodict
"""

import tempfile
import os
import time
import statistics
from typing import List, Tuple

try:
    import xmltodict
    HAS_XMLTODICT = True
except ImportError:
    HAS_XMLTODICT = False
    print("ERROR: xmltodict required for benchmarking - install with: pip install xmltodict")
    exit(1)

from xml_iterator.core import xml_to_dict


def create_test_xml(num_items: int) -> str:
    """Create XML file with specified number of items"""
    fd, path = tempfile.mkstemp(suffix='.xml')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
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
            f.write('</catalog>\n')
        return path
    except:
        os.close(fd)
        raise


def time_function(func, *args, num_runs: int = 5) -> Tuple[float, float]:
    """Time function execution with multiple runs"""
    times = []
    for _ in range(num_runs):
        start = time.perf_counter()
        result = func(*args)
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
                with open(filepath, 'r') as f:
                    return xmltodict.parse(f.read())
            
            xml_mean, xml_std = time_function(xmltodict_parse, xml_file, num_runs=5)
            
            # Calculate speedup
            speedup = xml_mean / our_mean if our_mean > 0 else float('inf')
            
            results.append({
                'size': size,
                'file_size_mb': file_size_mb,
                'our_time': our_mean,
                'our_std': our_std,
                'xml_time': xml_mean,
                'xml_std': xml_std,
                'speedup': speedup
            })
            
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
        print(f"{r['size']:<8} {r['file_size_mb']:<10.2f} {r['our_time']:<15.3f} {r['xml_time']:<15.3f} {r['speedup']:<10.2f}")
    
    print("-" * 80)
    
    # Summary statistics
    avg_speedup = statistics.mean([r['speedup'] for r in results])
    print(f"\nSummary:")
    print(f"Average speedup: {avg_speedup:.2f}x")
    
    if avg_speedup > 1.0:
        print(f"✅ xml_iterator is {avg_speedup:.1f}x faster than xmltodict on average")
    else:
        print(f"⚠️  xml_iterator is {1/avg_speedup:.1f}x slower than xmltodict on average")
    
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
        print(f"Streaming advantage:     {dict_time/stream_time:.1f}x faster for early termination")
        
    finally:
        os.unlink(xml_file)


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
                with open(filepath, 'r') as f:
                    return xmltodict.parse(f.read())
            
            xml_mean, _ = time_function(xmltodict_parse, xml_file, num_runs=3)
            speedup = xml_mean / our_mean if our_mean > 0 else float('inf')
            
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


if __name__ == "__main__":
    if not HAS_XMLTODICT:
        exit(1)
        
    benchmark_xmltodict_compatibility()
    benchmark_streaming_vs_dict()
    generate_readme_table()