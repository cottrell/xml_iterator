---
id: TASK-4
title: 'Document infinite depth attack (FIRDS) and acceptance tests'
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
**Infinite depth attack** is the core threat model: useful content sits under outer elements that stay open until late/EOF (FIRDS: wrappers, then millions of records at that depth). Tree/DOM consumers must wait for outer close or retain the whole open tree. Streaming yields child completion while ancestors remain open.

Reference: `backlog/docs/streaming-memory-model-and-landscape.md`.

Document that definition (keep the name), add FIRDS-shape regression/example, do not treat full-file `xml_to_dict` as the large-file path.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 README/AGENTS define infinite depth attack with FIRDS-like diagram; link or summarize the backlog doc
- [ ] #2 Protection described as streaming at depth under open outers + user discard/early stop — not primarily max_depth caps
- [ ] #3 Test or example: many records under wrappers that close at EOF; record ends before outer ends; early break after K works
- [ ] #4 Docs: full `xml_to_dict` is modest files / parity only, not multi-GB FIRDS-as-one-tree
- [ ] #5 Optional: landscape note (ET.iterparse, bigxml, xmltodict item_depth)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Read `backlog/docs/streaming-memory-model-and-landscape.md` (use project definition of infinite depth; do not rename away from it).
2. Minimal doc edits in README/AGENTS.
3. Synthetic FIRDS-shape test under tests/.
4. Optional examples/ snippet for record-at-a-time under open wrappers.
<!-- SECTION:PLAN:END -->
