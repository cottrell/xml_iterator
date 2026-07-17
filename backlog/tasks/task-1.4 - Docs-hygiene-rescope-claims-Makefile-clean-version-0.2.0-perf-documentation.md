---
id: TASK-1.4
title: >-
  Docs/hygiene: rescope claims, Makefile clean, version 0.2.0, perf
  documentation
status: Done
assignee:
  - '@claude-fable-5'
created_date: '2026-07-17 11:12'
updated_date: '2026-07-17 11:32'
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
- [x] #1 Docs claims match actual behavior
- [x] #2 make clean cannot delete .venv/target .so files
- [x] #3 Before/after benchmark numbers documented
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Key discovery during benchmarking: make develop built DEBUG extension (~9x slower drain); this poisoned all historical numbers including the review's '3x slower than ET.iterparse' claim — release build is 2.5x FASTER (2.6s vs 6.6s SwissProt). Makefile develop now uses --release; develop-debug added. PERF_2026-07-17.md documents before/after; REVIEW addendum corrects the record.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
README/CLAUDE.md/AGENTS.md rescoped (no 100%/graceful/production-ready claims; honest ET.iterparse comparison with release-build numbers); make clean prunes .venv+target (verified via find dry-run); version 0.2.0; PERF_2026-07-17.md with before/after tables.
<!-- SECTION:FINAL_SUMMARY:END -->
