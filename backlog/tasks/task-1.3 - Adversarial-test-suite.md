---
id: TASK-1.3
title: Adversarial test suite
status: Done
assignee:
  - '@claude-fable-5'
created_date: '2026-07-17 11:12'
updated_date: '2026-07-17 11:32'
labels: []
dependencies: []
parent_task_id: TASK-1
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
New tests/test_adversarial.py per GROK_RESPONSE.md list: self-closing tags through iter_xml/both get_edge_counts/xml_to_dict/read_records; malformed mid-file raises; ISO-8859-1 without BOM raises; UTF-16 with BOM works; CDATA preserved; attributes match xmltodict; max_depth consistency; depth past recursionlimit; no stdout pollution. Update tests/test_basic.py malformed expectations to require raising.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 All new adversarial tests pass
- [x] #2 Existing suite passes (updated where old behavior was the bug)
<!-- AC:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
tests/test_adversarial.py added (17 tests: self-closing, malformed-raises, encodings, CDATA, attributes incl. exact xmltodict comparison, max_depth, depth-5000, stdout hygiene); test_basic.py malformed test now requires ValueError. Full suite 37 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
