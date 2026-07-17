#!/usr/bin/env python
"""Parity tests: Rust xml_to_dict vs Python reference vs xmltodict."""

import os
import tempfile

import pytest

from xml_iterator.core import xml_to_dict, xml_to_dict_py

try:
    import xmltodict

    HAS_XMLTODICT = True
except ImportError:
    HAS_XMLTODICT = False


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


DOCS = {
    'attribute_rich': """<?xml version="1.0"?>
<root>
    <item id="1" type="a">
        <name>First</name>
    </item>
    <item id="2" type="b">
        <name>Second</name>
    </item>
    <x a="1"/>
    <mixed a="1" b="2">some text<child>c</child></mixed>
    <nested><a><b><c>deep</c></b></a></nested>
</root>""",
    'root_self_closing': '<r a="1" b="2"/>',
    'mixed_text_children': '<r>hello<a>1</a>world<b>2</b></r>',
    'empty_root': '<r/>',
}

BREAKFAST_MENU = """<?xml version="1.0" encoding="UTF-8"?>
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


class TestRustPythonParity:
    @pytest.mark.parametrize('name', sorted(DOCS.keys()))
    def test_parity_docs(self, name):
        xml_file = create_test_xml(DOCS[name])
        try:
            rust_result = xml_to_dict(xml_file)
            py_result = xml_to_dict_py(xml_file)
            assert rust_result == py_result
            if HAS_XMLTODICT:
                with open(xml_file, 'r') as f:
                    xmltodict_result = xmltodict.parse(f.read())
                assert rust_result == xmltodict_result
        finally:
            os.unlink(xml_file)

    def test_breakfast_menu(self):
        xml_file = create_test_xml(BREAKFAST_MENU)
        try:
            rust_result = xml_to_dict(xml_file)
            py_result = xml_to_dict_py(xml_file)
            assert rust_result == py_result
            if HAS_XMLTODICT:
                with open(xml_file, 'r') as f:
                    xmltodict_result = xmltodict.parse(f.read())
                assert rust_result == xmltodict_result
        finally:
            os.unlink(xml_file)

    @pytest.mark.parametrize('max_depth', [1, 2, 3])
    def test_max_depth_parity(self, max_depth):
        xml_content = '<r><deep><x><y>v</y></x></deep><flat>f</flat></r>'
        xml_file = create_test_xml(xml_content)
        try:
            rust_result = xml_to_dict(xml_file, max_depth=max_depth)
            py_result = xml_to_dict_py(xml_file, max_depth=max_depth)
            assert rust_result == py_result
        finally:
            os.unlink(xml_file)

    def test_max_events_partial_tree(self):
        xml_content = '<r><a><b>1</b><c>2</c></a><d>3</d></r>'
        xml_file = create_test_xml(xml_content)
        try:
            for max_events in (1, 3, 5, 8, 100):
                rust_result = xml_to_dict(xml_file, max_events=max_events)
                py_result = xml_to_dict_py(xml_file, max_events=max_events)
                assert isinstance(rust_result, dict)
                assert rust_result == py_result
        finally:
            os.unlink(xml_file)

    def test_deep_document_no_recursion_limit(self):
        depth = 5000
        xml_content = '<root>' + '<a>' * depth + 'v' + '</a>' * depth + '</root>'
        xml_file = create_test_xml(xml_content)
        try:
            result = xml_to_dict(xml_file)
            assert 'root' in result
        finally:
            os.unlink(xml_file)

    def test_malformed_raises_value_error(self):
        xml_content = '<root><a>1</a><b>unterminated'
        xml_file = create_test_xml(xml_content)
        try:
            with pytest.raises(ValueError):
                xml_to_dict(xml_file)
        finally:
            os.unlink(xml_file)
