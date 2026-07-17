---
id: TASK-1
title: 'Address 2026-07-17 review findings (correctness, parity, docs, perf)'
status: In Progress
assignee:
  - '@claude-fable-5'
created_date: '2026-07-17 11:12'
updated_date: '2026-07-17 11:12'
labels: []
dependencies: []
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
REVIEW_2026-07-17.md (Fable 5) and GROK_RESPONSE.md (Grok) independently confirmed correctness bugs and overstated docs claims. Fix wrong-answer paths first, then crashes, then docs/hygiene, then cheap perf wins. Breaking behavior changes (errors now raised, attributes emitted) bump version to 0.2.0.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All reproduced bugs from REVIEW_2026-07-17.md fixed with regression tests
- [ ] #2 Docs no longer claim 100% compatibility / graceful fallbacks / production ready inaccurately
- [ ] #3 Before/after performance documented
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Spec written by Fable 5 (orchestrator); implementation delegated to a Sonnet subagent for cost. 2. Rust src/lib.rs: error propagation (PyValueError), CDATA-as-text, empty-event fix in get_edge_counts + allow_threads, remove println!, buffer reuse, interned event names, opt-in attribute events. 3. Python core.py: max_depth skip-counter, iterative normalize, xmltodict attribute parity, empty handling, dead-code removal. 4. tests/test_adversarial.py + update stale expectations. 5. Docs rescope + make clean scoping + 0.2.0. 6. Rebuild, full pytest, re-run probe scripts from review, before/after benchmarks documented. Fable reviews the full diff before commit.
<!-- SECTION:PLAN:END -->
