---
id: TASK-1.4
title: >-
  Docs/hygiene: rescope claims, Makefile clean, version 0.2.0, perf
  documentation
status: In Progress
assignee:
  - '@claude-fable-5'
created_date: '2026-07-17 11:12'
updated_date: '2026-07-17 11:12'
labels: []
dependencies: []
parent_task_id: TASK-1
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
README.md, CLAUDE.md, AGENTS.md (outside managed comment blocks): drop '100% xmltodict compatibility' (rescope to: parity including attributes, namespaces/prefixes still stripped), 'graceful fallbacks' (now: errors raised), 'production ready'; reframe 734x as generic streaming early-exit; add honest ET.iterparse comparison. Scope make clean find to exclude .venv and target. Bump Cargo.toml to 0.2.0. After implementation, re-run benchmarks and document before/after performance in REVIEW file or new PERF note.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Docs claims match actual behavior
- [ ] #2 make clean cannot delete .venv/target .so files
- [ ] #3 Before/after benchmark numbers documented
<!-- AC:END -->
