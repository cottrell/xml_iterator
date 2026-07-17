---
id: TASK-1.3
title: Adversarial test suite
status: In Progress
assignee:
  - '@claude-fable-5'
created_date: '2026-07-17 11:12'
updated_date: '2026-07-17 11:12'
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
- [ ] #1 All new adversarial tests pass
- [ ] #2 Existing suite passes (updated where old behavior was the bug)
<!-- AC:END -->
