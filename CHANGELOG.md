# Changelog

## 0.2.1 (2026-07-17)

- Benchmark suite: stream backends (`et_iterparse`, `sax`, `lxml_iterparse`) vs `xml_iterator`,
  shared `bench_common.py`, results JSON, README tables auto-rendered from JSON.
- `make show-benchmarks` / `scripts/print_benchmarks.py` pretty-print last results (stdlib).
- `make readme-benchmarks` / `scripts/update_readme_benchmarks.py` rewrite README from JSON.
- Early-exit vs full-drain treated as separate tasks; **SAX is N/A for early-exit** (adapter
  materializes the full parse first) and for large full drains.
- Commit `benchmark_data/benchmark_results.json` snapshot (SwissProt / FIRDS / synthetic).

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
