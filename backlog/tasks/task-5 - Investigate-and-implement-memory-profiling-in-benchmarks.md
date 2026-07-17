---
id: TASK-5
title: Investigate and implement memory profiling in benchmarks
status: To Do
assignee: []
created_date: '2026-07-17 12:27'
labels: []
dependencies: []
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
