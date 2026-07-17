---
id: DRAFT-1
title: Investigate and implement memory profiling in benchmarks
status: Draft
assignee: []
created_date: '2026-07-17 12:27'
updated_date: '2026-07-17 12:52'
labels:
  - deferred
  - do-not-do-now
dependencies: []
priority: low
type: task
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Analyze the benchmark scripts and test suite to verify whether memory profiling is present (our initial scan shows it is not programmatically measured; it only prints text asserting constant memory).
Implement a robust memory profiling approach. Note that because `xml_iterator` runs Rust code via PyO3, Python-only tools like `tracemalloc` will not capture Rust heap allocations. We should use process-level tracking like peak RSS via `resource.getrusage` (Unix) or `psutil` to capture both Python and Rust memory.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Compare peak memory (RSS) of `xml_iterator` vs `xmltodict` and `xml.etree.ElementTree` in real-world benchmarks.
- [ ] #2 Verify that streaming with early termination uses constant/flat memory even for larger files.
- [ ] #3 Integrate memory reporting into `benchmark.py` and `benchmark_real_world.py` output.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
DEFERRED / DO NOT DO NOW (2026-07-17).

Decision: skip for now. Not hard (stdlib resource.getrusage + subprocess peaks would suffice), but low product value vs correctness/perf work, and AC #2 (“prove constant memory”) is soft/noisy with peak RSS. Fake checkmark in benchmark_real_world.benchmark_memory_efficiency is known; fix only when we care about honest memory numbers in README/benches.

When revived: process-level peak RSS in fresh subprocesses; report MB/ratios (not “proves constant”); no memray/psutil required for v1. Do not use tracemalloc (misses Rust/PyO3 heap).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: grok
created: 2026-07-17 12:52
---
Deferred after review: not blocking; archive rather than leave as active To Do. Revive only if shipping stronger memory claims.
---
<!-- COMMENTS:END -->
