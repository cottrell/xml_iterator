---
id: TASK-1.1
title: >-
  Rust core: raise on errors, CDATA as text, fix empty panic, opt-in attributes,
  perf
status: In Progress
assignee:
  - '@claude-fable-5'
created_date: '2026-07-17 11:12'
updated_date: '2026-07-17 11:12'
labels: []
dependencies: []
parent_task_id: TASK-1
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
src/lib.rs: (1) parse errors and invalid UTF-8 must raise PyValueError, not fake EOF (.ok()? pattern); (2) undecodable/unescapable text raises instead of silent skip; (3) Event::CData yielded as text event; (4) get_edge_counts handles empty events (count without stack push) instead of panic!("what"), and releases the GIL during the scan; (5) remove println! on open; (6) reuse read buffer across next() calls; intern event-name strings; (7) iter_xml(path, attributes=False) opt-in kwarg emitting (count,'attr',(name,value)) events after start/empty; (8) delete dead commented-out code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Malformed mid-file XML raises ValueError from iteration, not silent stop
- [ ] #2 Latin-1 declared encoding without BOM raises, not silent text drop
- [ ] #3 CDATA content appears as text events
- [ ] #4 get_edge_counts on <root><a/></root> returns counts including the empty tag, no panic
- [ ] #5 No stdout output on normal open
- [ ] #6 iter_xml(path, attributes=True) yields attr events; default unchanged 3-tuples
<!-- AC:END -->
