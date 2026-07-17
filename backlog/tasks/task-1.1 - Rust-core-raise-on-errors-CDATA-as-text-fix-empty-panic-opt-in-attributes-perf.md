---
id: TASK-1.1
title: >-
  Rust core: raise on errors, CDATA as text, fix empty panic, opt-in attributes,
  perf
status: Done
assignee:
  - '@claude-fable-5'
created_date: '2026-07-17 11:12'
updated_date: '2026-07-17 11:32'
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
- [x] #1 Malformed mid-file XML raises ValueError from iteration, not silent stop
- [x] #2 Latin-1 declared encoding without BOM raises, not silent text drop
- [x] #3 CDATA content appears as text events
- [x] #4 get_edge_counts on <root><a/></root> returns counts including the empty tag, no panic
- [x] #5 No stdout output on normal open
- [x] #6 iter_xml(path, attributes=True) yields attr events; default unchanged 3-tuples
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented by Sonnet subagent per Fable spec; diff reviewed by Fable. Verified: pytest 37 passed; probe scripts confirm ValueError on malformed mid-file and Latin-1-no-BOM, CDATA-as-text, empty-tag counting, attr events, silent stdout. Deviation: added open_depth EOF check since quick-xml 0.26 does not flag truncated docs.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
src/lib.rs redesigned: Result-based iterator raising PyValueError (no silent EOF), CDATA as text, empty handled in get_edge_counts (panic removed) with allow_threads, println! removed, buffer reuse + interned event names, opt-in attr events. Verified via tests/test_adversarial.py + full suite (37 passed).
<!-- SECTION:FINAL_SUMMARY:END -->
