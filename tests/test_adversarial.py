#!/usr/bin/env python
"""
Adversarial tests: self-closing tags, malformed XML, encodings, CDATA,
attributes, max_depth, deep nesting, stdout hygiene.
"""

import os
import tempfile

import pytest

from xml_iterator.core import get_edge_counts as py_get_edge_counts
from xml_iterator.core import read_records, xml_to_dict
from xml_iterator.xml_iterator import get_edge_counts, iter_xml

try:
    import xmltodict

    HAS_XMLTODICT = True
except ImportError:
    HAS_XMLTODICT = False


def create_test_xml(content, mode='w', encoding='utf-8'):
    fd, path = tempfile.mkstemp(suffix='.xml')
    try:
        if mode == 'wb':
            with os.fdopen(fd, 'wb') as f:
                f.write(content)
        else:
            with os.fdopen(fd, 'w', encoding=encoding) as f:
                f.write(content)
        return path
    except Exception:
        os.close(fd)
        raise


class TestSelfClosingTags:
    def test_iter_xml_no_panic(self):
        xml_file = create_test_xml('<root><a/><b>hi</b></root>')
        try:
            events = list(iter_xml(xml_file))
            assert ('empty', 'a') in [(e, v) for _, e, v in events]
        finally:
            os.unlink(xml_file)

    def test_rust_get_edge_counts(self):
        xml_file = create_test_xml('<root><a/><b>hi</b></root>')
        try:
            counts = get_edge_counts(xml_file)
            assert counts[('root', 'a')] == 1
            assert counts[('root', 'b')] == 1
        finally:
            os.unlink(xml_file)

    def test_python_get_edge_counts(self):
        xml_file = create_test_xml('<root><a/><b>hi</b></root>')
        try:
            counts = py_get_edge_counts(xml_file)
            assert counts[('root', 'a')] == 1
            assert counts[('root', 'b')] == 1
        finally:
            os.unlink(xml_file)

    def test_edge_counts_agree(self):
        xml_file = create_test_xml('<root><a/><b>hi</b></root>')
        try:
            assert get_edge_counts(xml_file) == py_get_edge_counts(xml_file)
        finally:
            os.unlink(xml_file)

    def test_xml_to_dict(self):
        xml_file = create_test_xml('<root><a/><b>hi</b></root>')
        try:
            result = xml_to_dict(xml_file)
            assert result == {'root': {'a': None, 'b': 'hi'}}
        finally:
            os.unlink(xml_file)

    def test_read_records(self):
        xml_file = create_test_xml('<root><a/><b>hi</b></root>')
        try:
            out, counter = read_records(xml_file)
            assert counter[('root', 'a')] == 1
            assert counter[('root', 'b')] == 1
        finally:
            os.unlink(xml_file)


class TestMalformedXML:
    def test_iter_xml_raises(self):
        xml_file = create_test_xml('<root><a>one</a><b>two</WRONG><c>x</c></root>')
        try:
            with pytest.raises(ValueError):
                list(iter_xml(xml_file))
        finally:
            os.unlink(xml_file)

    def test_xml_to_dict_raises(self):
        xml_file = create_test_xml('<root><a>one</a><b>two</WRONG><c>x</c></root>')
        try:
            with pytest.raises(ValueError):
                xml_to_dict(xml_file)
        finally:
            os.unlink(xml_file)

    def test_rust_get_edge_counts_raises(self):
        xml_file = create_test_xml('<root><a>one</a><b>two</WRONG><c>x</c></root>')
        try:
            with pytest.raises(ValueError):
                get_edge_counts(xml_file)
        finally:
            os.unlink(xml_file)


class TestEncoding:
    def test_latin1_declared_no_bom_raises(self):
        content = '<?xml version="1.0" encoding="ISO-8859-1"?><r><a>café</a></r>'
        xml_file = create_test_xml(content.encode('latin-1'), mode='wb')
        try:
            with pytest.raises(ValueError):
                list(iter_xml(xml_file))
        finally:
            os.unlink(xml_file)

    def test_utf16_with_bom_parses(self):
        content = '<?xml version="1.0"?><r><a>hello world</a></r>'
        xml_file = create_test_xml(content.encode('utf-16'), mode='wb')
        try:
            events = list(iter_xml(xml_file))
            texts = [v for _, e, v in events if e == 'text']
            assert texts == ['hello world']
        finally:
            os.unlink(xml_file)


class TestCData:
    def test_cdata_preserved(self):
        xml_file = create_test_xml('<a><![CDATA[x < y & z]]></a>')
        try:
            events = list(iter_xml(xml_file))
            texts = [v for _, e, v in events if e == 'text']
            assert texts == ['x < y & z']
        finally:
            os.unlink(xml_file)

    def test_xml_to_dict_keeps_cdata(self):
        xml_file = create_test_xml('<a><![CDATA[x < y & z]]></a>')
        try:
            assert xml_to_dict(xml_file) == {'a': 'x < y & z'}
        finally:
            os.unlink(xml_file)


class TestAttributes:
    def test_default_no_attr_events(self):
        xml_file = create_test_xml('<r><a x="1">hi</a></r>')
        try:
            events = list(iter_xml(xml_file))
            assert not any(e == 'attr' for _, e, _ in events)
        finally:
            os.unlink(xml_file)

    def test_attributes_true_yields_attr_events(self):
        xml_file = create_test_xml('<r><a x="1" y="2">hi</a></r>')
        try:
            events = list(iter_xml(xml_file, attributes=True))
            attrs = [v for _, e, v in events if e == 'attr']
            assert attrs == [('x', '1'), ('y', '2')]
        finally:
            os.unlink(xml_file)

    @pytest.mark.skipif(not HAS_XMLTODICT, reason="xmltodict library not available")
    def test_xml_to_dict_matches_xmltodict_with_attrs(self):
        content = (
            '<r>'
            '<item id="1" ccy="EUR">100</item>'
            '<item id="2">200</item>'
            '<also_empty a="x"/>'
            '<empty></empty>'
            '</r>'
        )
        xml_file = create_test_xml(content)
        try:
            ours = xml_to_dict(xml_file)
            theirs = xmltodict.parse(open(xml_file).read())
            assert ours == theirs
        finally:
            os.unlink(xml_file)


class TestMaxDepth:
    def test_no_sibling_absorption(self):
        content = '<r><deep><x><y>v</y></x></deep><flat>f</flat></r>'
        xml_file = create_test_xml(content)
        try:
            result = xml_to_dict(xml_file, max_depth=2)
            assert result == {'r': {'deep': None, 'flat': 'f'}}
        finally:
            os.unlink(xml_file)


class TestDeepNesting:
    def test_xml_to_dict_depth_5000(self):
        depth = 5000
        content = '<r>' + '<a>' * depth + 'x' + '</a>' * depth + '</r>'
        xml_file = create_test_xml(content)
        try:
            result = xml_to_dict(xml_file)
            assert isinstance(result, dict)
        finally:
            os.unlink(xml_file)

    def test_iter_xml_depth_5000_drains(self):
        depth = 5000
        content = '<r>' + '<a>' * depth + 'x' + '</a>' * depth + '</r>'
        xml_file = create_test_xml(content)
        try:
            events = list(iter_xml(xml_file))
            assert len(events) > 0
        finally:
            os.unlink(xml_file)


class TestNoStdoutPollution:
    def test_iter_xml_silent(self, capfd):
        xml_file = create_test_xml('<r><a>hi</a></r>')
        try:
            list(iter_xml(xml_file))
            out, _err = capfd.readouterr()
            assert out == ''
        finally:
            os.unlink(xml_file)
