#!/usr/bin/env python
"""
xmltodict compatibility tests with strict exact comparisons
"""

import json
import os
import tempfile
import pytest

from xml_iterator.core import xml_to_dict

# Import xmltodict for comparison
try:
    import xmltodict
    HAS_XMLTODICT = True
except ImportError:
    HAS_XMLTODICT = False
    pytestmark = pytest.mark.skip(reason="xmltodict library not available")


def create_test_xml(content):
    """Create temporary XML file for testing"""
    fd, path = tempfile.mkstemp(suffix='.xml')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        return path
    except:
        os.close(fd)
        raise


@pytest.mark.skipif(not HAS_XMLTODICT, reason="xmltodict library not available")
class TestXMLtoDictCompatibility:
    """Test exact compatibility with xmltodict library"""
    
    def test_simple_structure_exact(self):
        """Test basic XML structure with EXACT comparison"""
        xml_content = """<?xml version="1.0"?>
<person>
    <name>John Doe</name>
    <age>30</age>
    <city>New York</city>
</person>"""
        
        xml_file = create_test_xml(xml_content)
        try:
            # Our implementation
            our_result = xml_to_dict(xml_file)
            
            # xmltodict comparison
            with open(xml_file, 'r') as f:
                xmltodict_result = xmltodict.parse(f.read())
            
            # EXACT comparison
            assert our_result == xmltodict_result, (
                f"Results don't match!\n"
                f"Ours: {json.dumps(our_result, indent=2)}\n"
                f"xmltodict: {json.dumps(xmltodict_result, indent=2)}"
            )
            
        finally:
            os.unlink(xml_file)

    def test_repeated_elements_exact(self):
        """Test XML with repeated elements - EXACT comparison"""
        xml_content = """<?xml version="1.0"?>
<catalog>
    <book>
        <title>Book 1</title>
        <author>Author 1</author>
    </book>
    <book>
        <title>Book 2</title>
        <author>Author 2</author>
    </book>
</catalog>"""
        
        xml_file = create_test_xml(xml_content)
        try:
            our_result = xml_to_dict(xml_file)
            
            with open(xml_file, 'r') as f:
                xmltodict_result = xmltodict.parse(f.read())
            
            # EXACT comparison
            assert our_result == xmltodict_result, (
                f"Results don't match!\n"
                f"Ours: {json.dumps(our_result, indent=2)}\n"
                f"xmltodict: {json.dumps(xmltodict_result, indent=2)}"
            )
            
        finally:
            os.unlink(xml_file)

    def test_text_only_element_exact(self):
        """Test simple text-only elements - EXACT comparison"""
        xml_content = """<?xml version="1.0"?>
<message>Hello World</message>"""
        
        xml_file = create_test_xml(xml_content)
        try:
            our_result = xml_to_dict(xml_file)
            
            with open(xml_file, 'r') as f:
                xmltodict_result = xmltodict.parse(f.read())
            
            assert our_result == xmltodict_result, (
                f"Results don't match!\n"
                f"Ours: {json.dumps(our_result, indent=2)}\n"
                f"xmltodict: {json.dumps(xmltodict_result, indent=2)}"
            )
            
        finally:
            os.unlink(xml_file)

    def test_empty_elements_exact(self):
        """Test empty elements including self-closing tags - EXACT comparison"""
        xml_content = """<?xml version="1.0"?>
<root>
    <empty></empty>
    <also_empty/>
</root>"""
        
        xml_file = create_test_xml(xml_content)
        try:
            our_result = xml_to_dict(xml_file)
            
            with open(xml_file, 'r') as f:
                xmltodict_result = xmltodict.parse(f.read())
            
            assert our_result == xmltodict_result, (
                f"Results don't match!\n"
                f"Ours: {json.dumps(our_result, indent=2)}\n"
                f"xmltodict: {json.dumps(xmltodict_result, indent=2)}"
            )
            
        finally:
            os.unlink(xml_file)

    def test_breakfast_menu_exact(self):
        """Test breakfast menu example - EXACT comparison"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<breakfast_menu>
  <food>
    <name>Belgian Waffles</name>
    <price>$5.95</price>
    <description>Two of our famous Belgian Waffles with plenty of real maple syrup</description>
    <calories>650</calories>
  </food>
  <food>
    <name>Strawberry Belgian Waffles</name>
    <price>$7.95</price>
    <description>Light Belgian waffles covered with strawberries and whipped cream</description>
    <calories>900</calories>
  </food>
</breakfast_menu>"""
        
        xml_file = create_test_xml(xml_content)
        try:
            our_result = xml_to_dict(xml_file)
            
            with open(xml_file, 'r') as f:
                xmltodict_result = xmltodict.parse(f.read())
            
            assert our_result == xmltodict_result, (
                f"Results don't match!\n"
                f"Our result keys: {list(our_result.keys()) if isinstance(our_result, dict) else type(our_result)}\n"
                f"xmltodict keys: {list(xmltodict_result.keys()) if isinstance(xmltodict_result, dict) else type(xmltodict_result)}"
            )
            
        finally:
            os.unlink(xml_file)

    def test_protection_limits(self):
        """Test max_depth and max_events protection parameters"""
        # Create deeply nested XML
        xml_content = '<?xml version="1.0"?>'
        depth = 50
        for i in range(depth):
            xml_content += f'<level{i}>'
        xml_content += '<content>deep value</content>'
        for i in range(depth - 1, -1, -1):
            xml_content += f'</level{i}>'
        
        xml_file = create_test_xml(xml_content)
        try:
            # Test with depth limit
            limited_result = xml_to_dict(xml_file, max_depth=10)
            
            # Test with event limit
            event_limited = xml_to_dict(xml_file, max_events=50)
            
            # Full parse
            full_result = xml_to_dict(xml_file)
            
            # Verify limits work
            assert limited_result != full_result or event_limited != full_result, (
                "Protection limits should affect parsing results"
            )
            
        finally:
            os.unlink(xml_file)