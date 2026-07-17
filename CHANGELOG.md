# Changelog

## 0.2.13 (2026-07-17)

Proper package version bump (Cargo). Tags `v0.2.11` / `v0.2.12` did not raise the
wheel version (still 0.2.1), so PyPI never got a new release from those tags.

- Benchmark suite: stream backends (`et_iterparse`, `sax`, `lxml_iterparse`) vs `xml_iterator`,
  shared `bench_common.py`, results JSON, README tables auto-rendered from JSON.
- `make show-benchmarks` / `scripts/print_benchmarks.py` pretty-print last results (stdlib).
- `make readme-benchmarks` / `scripts/update_readme_benchmarks.py` rewrite README from JSON.
- **One stream table per file:** full multi-backend drain if ≤150 MB (SwissProt); else early
  exit first 1M events only (FIRDS). Synthetic: large full drain + early-exit vs full dict.
- Early-exit caps large enough for signal (not 10 ms noise). **SAX is N/A for early-exit**
  (adapter materializes full parse first); SAX full drain skipped above 20 MB (RAM).
- Commit `benchmark_data/benchmark_results.json` snapshot; drop machine hostname from docs.

## 0.2.1 (2026-07-17)

Last PyPI release before 0.2.13. See tag `v0.2.1` / git history for that snapshot.

## 0.2.0 (2026-07-17)

- Malformed XML and undecodable text raise `ValueError` (no silent truncation).
- Attribute events opt-in: `iter_xml(path, attributes=True)` → `('attr', (name, value))`.
- `xml_iterator.xml_to_dict` includes attributes (`@name`) and matches `xmltodict.parse`; dict
  built in Rust (one FFI crossing). Python reference kept as `xml_to_dict_py` for parity tests.
- CDATA yielded as `text` events (was dropped).
- Self-closing tags (`<tag/>`) counted correctly by both `get_edge_counts` implementations.
- `xml_to_dict(max_depth=...)` no longer strands the stack / drops siblings.
- Normalization is iterative (no Python recursion limit on deep documents).
- `make develop` builds **release** by default; use `make develop-debug` for debug.

See [`PERF_2026-07-17.md`](PERF_2026-07-17.md) for measured impact.

## 0.1.x

Earlier streaming iterator + Python-side dict build; see git history.
