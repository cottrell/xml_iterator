---
id: TASK-4
title: Document infinite depth attack (FIRDS) and acceptance tests
status: Done
assignee:
  - '@grok'
created_date: '2026-07-17'
updated_date: '2026-07-17 12:26'
labels: []
dependencies: []
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
**Infinite depth attack** is the core threat model: useful content sits under outer elements that stay open until late/EOF (FIRDS: wrappers, then millions of records at that depth). Tree/DOM consumers must wait for outer close or retain the whole open tree. Streaming yields child completion while ancestors remain open.

Reference: `backlog/docs/streaming-memory-model-and-landscape.md`.

Document that definition (keep the name), add FIRDS-shape regression/example, do not treat full-file `xml_to_dict` as the large-file path.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 README/AGENTS define infinite depth attack with FIRDS-like diagram; link or summarize the backlog doc
- [x] #2 Protection described as streaming at depth under open outers + user discard/early stop — not primarily max_depth caps
- [x] #3 Test or example: many records under wrappers that close at EOF; record ends before outer ends; early break after K works
- [x] #4 Docs: full `xml_to_dict` is modest files / parity only, not multi-GB FIRDS-as-one-tree
- [x] #5 Optional: landscape note (ET.iterparse, bigxml, xmltodict item_depth)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Read `backlog/docs/streaming-memory-model-and-landscape.md` (use project definition of infinite depth; do not rename away from it).
2. Minimal doc edits in README/AGENTS.
3. Synthetic FIRDS-shape test under tests/.
4. Optional examples/ snippet for record-at-a-time under open wrappers.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implementing docs (README/AGENTS), FIRDS-shape regression test, optional example.

Docs: README/AGENTS/CLAUDE infinite depth + FIRDS diagram + xml_to_dict scope + landscape. Tests: tests/test_firds_shape.py (4 passed). Example: examples/firds_shape_stream.py.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Documented infinite depth attack (FIRDS shape) in README/AGENTS/CLAUDE with diagram and link to backlog/docs/streaming-memory-model-and-landscape.md. Protection framed as streaming under open outers + discard/early stop (not max_depth). Full xml_to_dict scoped to modest files/parity. Added tests/test_firds_shape.py (record ends before outers, 5k records, early break after K, discard consumer) — 4/4 pytest passed; examples/firds_shape_stream.py. Landscape table (ET.iterparse, bigxml, xmltodict item_depth) in README.
<!-- SECTION:FINAL_SUMMARY:END -->
