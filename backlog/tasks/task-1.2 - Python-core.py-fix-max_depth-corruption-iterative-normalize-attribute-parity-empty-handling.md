---
id: TASK-1.2
title: >-
  Python core.py: fix max_depth corruption, iterative normalize, attribute
  parity, empty handling
status: In Progress
assignee:
  - '@claude-fable-5'
created_date: '2026-07-17 11:12'
updated_date: '2026-07-17 11:12'
labels: []
dependencies: []
parent_task_id: TASK-1
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
xml_iterator/core.py: (1) xml_to_dict max_depth must skip whole subtrees without stranding the stack (no sibling absorption); (2) _normalize_dict iterative (no RecursionError at depth 5000+); (3) xml_to_dict consumes attr events by default and produces xmltodict-parity @attr/#text output; (4) get_edge_counts and read_records handle empty events (count self-closing tags, no raise); (5) delete unused experiments xml_to_dict_simple and reduce_length_one_lists_recursively (unused by tests/examples/benchmarks); (6) max_events/n_max use 'is not None' checks.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 xml_to_dict output equals xmltodict.parse on attribute-rich documents
- [ ] #2 max_depth=2 on <r><deep><x><y>v</y></x></deep><flat>f</flat></r> keeps flat
- [ ] #3 xml_to_dict succeeds at depth 5000
- [ ] #4 Python get_edge_counts counts self-closing tags
<!-- AC:END -->
