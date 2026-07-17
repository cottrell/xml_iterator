#!/usr/bin/env python
"""Comparator stream backends: same signature, open-under-parent event order."""

import os
import tempfile

from xml_iterator.comparators import available_stream_iterators, drain

try:
    import lxml.etree  # noqa: F401

    HAS_LXML = True
except ImportError:
    HAS_LXML = False


def create_test_xml(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        return path
    except Exception:
        os.close(fd)
        raise


FIRDS_SHAPE = """<?xml version="1.0"?>
<root>
  <list>
    <item id="1"><name>a</name></item>
    <item id="2"><name>b</name></item>
  </list>
</root>
"""

SIMPLE = """<?xml version="1.0"?>
<r>
  <b>x</b>
  <c>y</c>
</r>
"""


def _backend_names():
    return list(available_stream_iterators().keys())


def test_available_includes_core():
    names = available_stream_iterators()
    assert "xml_iterator" in names
    assert "et_iterparse" in names
    assert "sax" in names
    if HAS_LXML:
        assert "lxml_iterparse" in names


def test_signature_and_firds_order():
    """Child item ends before list/root; start before end for item."""
    path = create_test_xml(FIRDS_SHAPE)
    try:
        for backend_name, fn in available_stream_iterators().items():
            events = list(fn(path))
            assert events, backend_name
            for row in events:
                assert len(row) == 3
                count, event, value = row
                assert isinstance(count, int)
                assert event in ("start", "end", "empty", "text", "attr")
                if event == "attr":
                    assert isinstance(value, tuple) and len(value) == 2
                else:
                    assert isinstance(value, str)

            seq = [(e, v) for _, e, v in events if e in ("start", "end", "empty")]
            flat = []
            for e, v in seq:
                if e == "empty":
                    flat.append(("start", v))
                    flat.append(("end", v))
                else:
                    flat.append((e, v))

            def first(ev, tag, flat=flat):
                for i, (e, t) in enumerate(flat):
                    if e == ev and t == tag:
                        return i
                return None

            assert first("start", "item") is not None, backend_name
            assert first("start", "item") < first("end", "item"), backend_name
            assert first("end", "item") < first("end", "list"), backend_name
            assert first("end", "item") < first("end", "root"), backend_name
            item_ends = [i for i, (e, t) in enumerate(flat) if e == "end" and t == "item"]
            assert len(item_ends) == 2, backend_name
            assert all(i < first("end", "list") for i in item_ends), backend_name
    finally:
        os.unlink(path)


def test_attrs_on_start_when_requested():
    path = create_test_xml('<r><item id="1" ccy="EUR">100</item></r>')
    try:
        for backend_name, fn in available_stream_iterators().items():
            events = list(fn(path, attributes=True))
            attrs = [(v[0], v[1]) for _, e, v in events if e == "attr"]
            assert ("id", "1") in attrs, backend_name
            assert ("ccy", "EUR") in attrs, backend_name
            idx_start = next(i for i, (_, e, v) in enumerate(events) if e == "start" and v == "item")
            idx_end = next(i for i, (_, e, v) in enumerate(events) if e == "end" and v == "item")
            idx_attr = next(i for i, (_, e, v) in enumerate(events) if e == "attr" and v[0] == "id")
            assert idx_start < idx_attr < idx_end, backend_name
    finally:
        os.unlink(path)


def test_structural_tags_match_native_for_nonempty():
    """start/end/text sequence matches native after expanding empty."""
    path = create_test_xml(SIMPLE)
    try:
        native = list(available_stream_iterators()["xml_iterator"](path))

        def structure(events):
            out = []
            for _, e, v in events:
                if e == "empty":
                    out.append(("start", v))
                    out.append(("end", v))
                elif e in ("start", "end", "text"):
                    out.append((e, v))
            return out

        want = structure(native)
        for backend_name, fn in available_stream_iterators().items():
            if backend_name == "xml_iterator":
                continue
            other = list(fn(path))
            assert structure(other) == want, backend_name
    finally:
        os.unlink(path)


def test_drain_counts_positive():
    path = create_test_xml(SIMPLE)
    try:
        for backend_name in _backend_names():
            n = drain(path, backend_name)
            assert n >= 6, backend_name
            n2 = drain(path, backend_name, max_events=3)
            assert n2 == 3, backend_name
    finally:
        os.unlink(path)
