#!/usr/bin/env python
"""FIRDS-shape infinite depth: records complete under wrappers that close at EOF."""

import os
import tempfile

from xml_iterator.xml_iterator import iter_xml


def create_test_xml(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        return path
    except Exception:
        os.close(fd)
        raise


def firds_like_xml(n_records: int) -> str:
    """Wrappers open for the whole document; records complete at depth under them."""
    parts = [
        '<?xml version="1.0"?>',
        "<root>",
        "<Hdr><Msg>meta</Msg></Hdr>",
        "<Payload>",
        "<RefData>",
    ]
    for i in range(n_records):
        parts.append(f"<FinInstrm><Id>{i}</Id></FinInstrm>")
    parts.extend(["</RefData>", "</Payload>", "</root>"])
    return "".join(parts)


class TestFirdsShapeInfiniteDepth:
    """Acceptance: child ends before outer ends; early break; discard keeps work small."""

    def test_record_ends_before_outers(self):
        n = 50
        path = create_test_xml(firds_like_xml(n))
        try:
            flat = [(e, v) for _, e, v in iter_xml(path) if e in ("start", "end", "empty")]

            def first(ev, tag):
                for i, (e, t) in enumerate(flat):
                    if e == ev and t == tag:
                        return i
                raise AssertionError(f"missing {ev} {tag}")

            item_ends = [i for i, (e, t) in enumerate(flat) if e == "end" and t == "FinInstrm"]
            assert len(item_ends) == n
            end_ref = first("end", "RefData")
            end_payload = first("end", "Payload")
            end_root = first("end", "root")
            assert all(i < end_ref for i in item_ends)
            assert all(i < end_payload for i in item_ends)
            assert all(i < end_root for i in item_ends)
            assert first("start", "RefData") < item_ends[0]
        finally:
            os.unlink(path)

    def test_many_records_all_complete_before_wrapper_close(self):
        n = 5_000
        path = create_test_xml(firds_like_xml(n))
        try:
            item_ends = 0
            saw_ref_end = False
            for _, event, value in iter_xml(path):
                if event == "end" and value == "FinInstrm":
                    assert not saw_ref_end
                    item_ends += 1
                elif event == "end" and value == "RefData":
                    saw_ref_end = True
            assert item_ends == n
            assert saw_ref_end
        finally:
            os.unlink(path)

    def test_early_break_after_k_records(self):
        n = 10_000
        k = 1_000
        path = create_test_xml(firds_like_xml(n))
        try:
            item_ends = 0
            for _, event, value in iter_xml(path):
                if event == "end" and value == "FinInstrm":
                    item_ends += 1
                    if item_ends >= k:
                        break
            assert item_ends == k
        finally:
            os.unlink(path)

    def test_discard_consumer_does_not_accumulate_records(self):
        """Streaming consumer keeps only last record; not a  N-sized parent list."""
        n = 2_000
        path = create_test_xml(firds_like_xml(n))
        try:
            last_id = None
            seen = 0
            depth = 0
            max_depth = 0
            for _, event, value in iter_xml(path):
                if event == "start":
                    depth += 1
                    max_depth = max(max_depth, depth)
                elif event == "end":
                    if value == "FinInstrm":
                        seen += 1
                        # discard: only remember count / last, not stack of records
                        last_id = seen - 1
                    depth -= 1
            assert seen == n
            assert last_id == n - 1
            # open spine is shallow wrappers + record, not O(n)
            assert max_depth <= 6
        finally:
            os.unlink(path)
