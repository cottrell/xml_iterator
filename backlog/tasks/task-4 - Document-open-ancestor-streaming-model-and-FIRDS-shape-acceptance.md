---
id: TASK-4
title: 'Document open-ancestor streaming model and FIRDS-shape acceptance'
status: To Do
assignee: []
created_date: '2026-07-17'
updated_date: '2026-07-17'
labels: []
dependencies: []
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Origin problem is not mainly "infinite depth bombs" — it is **open-ancestor / breadth streaming**: FIRDS-like files open shallow wrappers near the start and only close them at EOF, with millions of record siblings underneath. Consumers must process each record on its own `end` without waiting for outer close and without retaining all siblings.

Reference write-up: `backlog/docs/streaming-memory-model-and-landscape.md` (includes landscape: iterparse, bigxml, xmltodict item_depth).

Rescope README/AGENTS language; add FIRDS-shape regression/example; do not treat full-file `xml_to_dict` as the large-file success path.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 README/AGENTS (or CLAUDE) state open-ancestor streaming as primary memory model; link or summarize the backlog doc
- [ ] #2 "Infinite depth protection" rephrased so depth caps are secondary; breadth under open parents is primary
- [ ] #3 Example or test: many sibling records under wrappers that close at EOF — record ends fire before outer ends; early break after K records works
- [ ] #4 Docs clarify full `xml_to_dict` is for modest files / parity, not multi-GB FIRDS-as-one-tree
- [ ] #5 Optional: note landscape alternatives (ET.iterparse, bigxml, xmltodict streaming) so build-vs-buy stays honest
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Read `backlog/docs/streaming-memory-model-and-landscape.md`.
2. Edit product docs only (minimal); avoid re-litigating completed task-1 bugfixes unless wording still wrong.
3. Add synthetic FIRDS-shape test (shallow wrappers + large sibling list) under tests/.
4. Optionally add `examples/` snippet for record-at-a-time consumption.
<!-- SECTION:PLAN:END -->
