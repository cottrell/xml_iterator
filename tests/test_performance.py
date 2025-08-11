#!/usr/bin/env python
"""
Performance regression tests for xml_iterator
"""

import os
import tempfile
import time
import pytest

from xml_iterator.xml_iterator import iter_xml
from xml_iterator.core import xml_to_dict


def create_large_xml(num_items=10000):
    """Create large XML file for testing"""
    fd, path = tempfile.mkstemp(suffix='.xml')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<catalog>\n')
            for i in range(num_items):
                f.write(
                    f'''  <book id="{i}">
    <title>Book Title {i}</title>
    <author>Author {i % 100}</author>
    <year>{2000 + (i % 24)}</year>
    <price>${(i % 50) + 10}.99</price>
    <description>Description for book {i} with some text content.</description>
  </book>
'''
                )
            f.write('</catalog>\n')
        return path
    except:
        os.close(fd)
        raise


class TestPerformanceRegression:
    """Performance regression tests - ensure no major slowdowns"""
    
    @pytest.mark.slow
    def test_large_file_streaming_performance(self):
        """Test that streaming performance meets basic thresholds"""
        xml_file = create_large_xml(5000)
        try:
            start_time = time.perf_counter()
            count = 0
            for event_count, event, value in iter_xml(xml_file):
                count += 1
            end_time = time.perf_counter()
            
            parse_time = end_time - start_time
            file_size_mb = os.path.getsize(xml_file) / 1024 / 1024
            
            # Basic performance threshold - should parse at least 1MB/second
            throughput = file_size_mb / parse_time
            assert throughput > 1.0, f"Throughput too low: {throughput:.2f} MB/s"
            assert count > 0, "No events parsed"
            
        finally:
            os.unlink(xml_file)

    @pytest.mark.slow  
    def test_dict_conversion_performance(self):
        """Test that xml_to_dict performance meets basic thresholds"""
        xml_file = create_large_xml(2000)
        try:
            start_time = time.perf_counter()
            result = xml_to_dict(xml_file)
            end_time = time.perf_counter()
            
            parse_time = end_time - start_time
            file_size_mb = os.path.getsize(xml_file) / 1024 / 1024
            
            # Dictionary conversion should be reasonable
            assert parse_time < 5.0, f"Dict conversion too slow: {parse_time:.2f}s"
            assert result is not None, "No result from xml_to_dict"
            assert isinstance(result, dict), "Result should be a dictionary"
            
        finally:
            os.unlink(xml_file)

    @pytest.mark.slow
    def test_streaming_early_termination_efficiency(self):
        """Test that early termination is efficient even with large files"""
        xml_file = create_large_xml(50000)  # Very large file
        try:
            # Test early termination - should use constant time regardless of file size
            start_time = time.perf_counter()
            count = 0
            for event_count, event, value in iter_xml(xml_file):
                count += 1
                if count >= 1000:  # Stop early
                    break
            end_time = time.perf_counter()
            
            # Should terminate quickly even with massive file
            parse_time = end_time - start_time
            assert parse_time < 0.5, f"Early termination too slow: {parse_time:.3f}s"
            assert count == 1000, f"Expected 1000 events, got {count}"
            
        finally:
            os.unlink(xml_file)

    def test_memory_usage_protection_limits(self):
        """Test that protection limits work as expected"""
        xml_file = create_large_xml(1000)
        try:
            # Test event limiting
            start_time = time.perf_counter()
            limited_result = xml_to_dict(xml_file, max_events=100)
            limited_time = time.perf_counter() - start_time
            
            start_time = time.perf_counter()
            full_result = xml_to_dict(xml_file)
            full_time = time.perf_counter() - start_time
            
            # Limited parsing should be faster than full parsing
            assert limited_time < full_time, "Limited parsing should be faster"
            assert limited_result != full_result, "Limited result should differ from full result"
            
        finally:
            os.unlink(xml_file)