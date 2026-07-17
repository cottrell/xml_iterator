---
id: TASK-2
title: 'Perf: move dict-building/aggregation into Rust or batch events across FFI'
status: In Progress
assignee:
  - '@claude-fable-5'
created_date: '2026-07-17 11:32'
updated_date: '2026-07-17 12:20'
labels: []
dependencies: []
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up from TASK-1 / PERF_2026-07-17.md. xml_to_dict on very large files (SwissProt 110MB: 20.4s vs xmltodict 12.9s) is dominated by the Python-side tree build; the Rust drain is only 2.6s. Options: build the dict in Rust with PyO3 (push/pop PyDicts on a Vec stack, cross the boundary once), Rust-side event filters, or batch N events per FFI crossing. Per-event FFI costs ~2x vs staying in Rust (get_edge_counts 1.3s vs drain 2.6s). Requires an API decision; benchmark against ET.iterparse and xmltodict on release builds only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 xml_to_dict faster than xmltodict on SwissProt-scale files
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Decision: build the dict in Rust (Option A from description) — consume the internal Rust event iterator inside a new #[pyfunction] xml_to_dict(path, max_depth=None, max_events=None), constructing PyDicts directly with a frame stack (lazy dict + text per frame, single/list promotion on repeated tags, @attr/#text xmltodict semantics, skip-counter max_depth, unwind on max_events). 2. core.py xml_to_dict delegates to Rust; Python impl kept as xml_to_dict_py for parity tests. 3. Parity tests rust-vs-python-vs-xmltodict; existing suite must stay green. 4. Implementation delegated to Sonnet subagent per Fable spec; Fable reviews diff. 5. AC verified on SwissProt release build vs xmltodict; PERF/docs updated.
<!-- SECTION:PLAN:END -->
