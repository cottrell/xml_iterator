"""Streaming XML iterators with the same profile as ``iter_xml``.

Signature (all backends)::

    iter_*(path: str, attributes: bool = False) -> Iterator[tuple[int, str, Any]]

Yields ``(count, event, value)`` where ``event`` is one of:

- ``start`` / ``end`` / ``empty`` / ``text`` — ``value`` is ``str``
- ``attr`` (only if ``attributes=True``) — ``value`` is ``(name, value)``

Backends that lack a true self-closing event emit ``start`` then ``end`` for
``<a/>`` (stdlib ET, lxml, SAX). ``xml_iterator`` emits ``empty``.

``xmltodict`` is not included: its streaming API dumps a completed dict at a
depth on close, not open-tag event streaming.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

EventRow = Tuple[int, str, Any]
StreamFn = Callable[..., Iterator[EventRow]]


def _local_tag(tag: str) -> str:
    if isinstance(tag, str) and tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag


def _attr_events(count: int, attrib: Dict[str, str]) -> Tuple[int, List[EventRow]]:
    rows: List[EventRow] = []
    for name, value in attrib.items():
        rows.append((count, "attr", (str(name), str(value))))
        count += 1
    return count, rows


def iter_xml_native(path: str, attributes: bool = False) -> Iterator[EventRow]:
    """This package's Rust ``iter_xml`` (reference)."""
    from xml_iterator.xml_iterator import iter_xml

    return iter_xml(path, attributes=attributes)


def iter_xml_et(path: str, attributes: bool = False) -> Iterator[EventRow]:
    """stdlib ``xml.etree.ElementTree.iterparse`` → same event triples.

    Self-closing tags become ``start`` + ``end`` (no ``empty``).
    Text is emitted from ``elem.text`` on ``end`` (trimmed); tails ignored.
    Finished elements are cleared to limit growth under open parents.
    """
    import xml.etree.ElementTree as ET

    count = 0
    for event, elem in ET.iterparse(path, events=("start", "end")):
        tag = _local_tag(elem.tag)
        if event == "start":
            yield (count, "start", tag)
            count += 1
            if attributes and elem.attrib:
                count, rows = _attr_events(count, dict(elem.attrib))
                for row in rows:
                    yield row
        else:
            text = elem.text
            if text is not None:
                trimmed = text.strip()
                if trimmed:
                    yield (count, "text", trimmed)
                    count += 1
            yield (count, "end", tag)
            count += 1
            elem.clear()


def iter_xml_lxml(path: str, attributes: bool = False) -> Iterator[EventRow]:
    """``lxml.etree.iterparse`` → same event triples. Optional dependency."""
    from lxml import etree

    count = 0
    for event, elem in etree.iterparse(path, events=("start", "end")):
        tag = _local_tag(elem.tag)
        if event == "start":
            yield (count, "start", tag)
            count += 1
            if attributes and elem.attrib:
                count, rows = _attr_events(count, {str(k): str(v) for k, v in elem.attrib.items()})
                for row in rows:
                    yield row
        else:
            text = elem.text
            if text is not None:
                trimmed = text.strip()
                if trimmed:
                    yield (count, "text", trimmed)
                    count += 1
            yield (count, "end", tag)
            count += 1
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]


def iter_xml_sax(path: str, attributes: bool = False) -> Iterator[EventRow]:
    """stdlib ``xml.sax`` → same event triples (materialized then iterated).

    SAX is push-based; we buffer the event list so the public API stays a
    plain iterator over ``(count, event, value)``. That means **early exit is
    not the same task** as true streaming: ``break`` after N still paid the
    full parse + list. Benches mark SAX N/A for early-exit; full drain only
    on modest files (multi-GB would hold all events in RAM).
    """
    import xml.sax
    from xml.sax.handler import ContentHandler

    rows: List[EventRow] = []
    count = 0

    class Handler(ContentHandler):
        def __init__(self) -> None:
            super().__init__()
            self._parts: List[str] = []

        def _flush_text(self) -> None:
            nonlocal count
            if not self._parts:
                return
            text = "".join(self._parts).strip()
            self._parts = []
            if text:
                rows.append((count, "text", text))
                count += 1

        def startElement(self, name, attrs):  # noqa: N802
            nonlocal count
            self._flush_text()
            rows.append((count, "start", name))
            count += 1
            if attributes:
                for aname in attrs.getNames():
                    rows.append((count, "attr", (aname, attrs.getValue(aname))))
                    count += 1

        def endElement(self, name):  # noqa: N802
            nonlocal count
            self._flush_text()
            rows.append((count, "end", name))
            count += 1

        def characters(self, content):
            self._parts.append(content)

    handler = Handler()
    xml.sax.parse(path, handler)
    return iter(rows)


def _try_lxml() -> Optional[StreamFn]:
    try:
        import lxml.etree  # noqa: F401
    except ImportError:
        return None
    return iter_xml_lxml


def available_stream_iterators() -> Dict[str, StreamFn]:
    """Name → callable for every stream backend importable in this env."""
    out: Dict[str, StreamFn] = {
        "xml_iterator": iter_xml_native,
        "et_iterparse": iter_xml_et,
        "sax": iter_xml_sax,
    }
    lxml_fn = _try_lxml()
    if lxml_fn is not None:
        out["lxml_iterparse"] = lxml_fn
    return out


def drain(path: str, name: str, attributes: bool = False, max_events: Optional[int] = None) -> int:
    """Consume a backend; return number of events seen."""
    fn = available_stream_iterators()[name]
    n = 0
    for _ in fn(path, attributes=attributes):
        n += 1
        if max_events is not None and n >= max_events:
            break
    return n
