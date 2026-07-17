---
id: TASK-3
title: Upgrade pyo3 (0.17 -> current) and quick-xml (0.26 -> current); abi3 wheels
status: To Do
assignee: []
created_date: '2026-07-17 11:32'
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
- [ ] #1 Builds and full test suite pass on upgraded deps
- [ ] #2 Declared non-UTF-8 encodings either parse correctly or still fail loudly
<!-- AC:END -->
