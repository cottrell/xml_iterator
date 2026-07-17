---
id: TASK-3
title: Upgrade pyo3 (0.17 -> current) and quick-xml (0.26 -> current); abi3 wheels
status: Done
assignee:
  - '@antigravity'
created_date: '2026-07-17 11:32'
updated_date: '2026-07-17 12:14'
labels: []
dependencies: []
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Deferred from TASK-1 to keep diffs minimal. pyo3 0.17 predates official Python 3.12 support (builds today but is legacy); newer pyo3 enables abi3 wheels matching the requires-python >=3.7 claim; quick-xml has parser perf work since 0.26 and an 'encoding' feature that could properly support declared non-UTF-8 encodings (currently a documented ValueError).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Builds and full test suite pass on upgraded deps
- [x] #2 Declared non-UTF-8 encodings either parse correctly or still fail loudly
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Update Cargo.toml to use pyo3 0.28.1 (with abi3-py37) and quick-xml 0.36.0 (with encoding).
2. Update src/lib.rs to:
   - Use PyOSError instead of PyIOError.
   - Implement PEP 489 / Bound API signature for #[pymodule] and #[pyfunction].
   - Wrap iterator in a Mutex to implement Sync.
   - Sniff BOM to selectively transcode UTF-16/BOM files while using direct BufReader and quick-xml's encoding feature for other declared encodings (e.g. ISO-8859-1).
   - Use reader.decoder() and quick-xml unescape module to decode and unescape text and tag names.
3. Compile and test the project.
4. Verify acceptance criteria.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Upgraded deps and resolved all PyO3 Bound API and quick-xml 0.36 changes. Implemented BOM sniffing so that only files with BOM (e.g. UTF-16 with BOM) are transcoded via DecodeReaderBytes, while other files (e.g. ISO-8859-1) are parsed directly by quick-xml using its encoding feature. Also wrapped the internal iterator in a Mutex so that PyXMLIterator is Send + Sync, which is required by newer PyO3 versions.

Fable review (claude-fable-5): upgrade itself solid (pyo3 0.28.1 Bound API, Mutex for Sync, abi3-py37 wheel verified: cp37-abi3-manylinux). Found one regression: UTF-16 files with BOM AND encoding='UTF-16' declaration (the common real-world shape) raised ValueError — DecodeReaderBytes transcoded to UTF-8 but quick-xml's encoding feature then honored the stale declaration and desynced its decoder. Note quick-xml cannot parse UTF-16 at all (encoding feature is ASCII-compatible-only), so raw passthrough was not an option either. Fixed by stripping the XML declaration from the transcoded UTF-16 stream (Cursor+chain head rewrite). Full encoding matrix probed (8 cases), 4 regression tests added, 46 tests green, SwissProt drain perf unchanged (2.60s vs 2.62s pre-upgrade).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Successfully upgraded pyo3 to 0.28.1 and quick-xml to 0.36.0. Rebuilt abi3 wheels targeting Python >=3.7. Verified that ISO-8859-1 files parse successfully without raising ValueError, and all 37/37 tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->
