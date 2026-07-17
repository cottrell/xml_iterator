# Changelog

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
