# xml_iterator

Streaming XML for Python. Primary goal: defeat the **infinite depth attack** on large
dumps where useful records sit under outer elements that stay open until
late/EOF — a tree/DOM consumer either waits for those outers or holds the whole open tree.

```text
<root>                              ← opens near start
  <Payload>
    <RefData>                       ← open for almost the whole file
      <FinInstrm> ... </FinInstrm>  ← record 1 complete (outers still open)
      <FinInstrm> ... </FinInstrm>  ← record 2
      ...
    </RefData>                      ← closes near EOF
  </Payload>
</root>
```

**Protection** is streaming under open wrappers plus **user discard / early stop** — not
`max_depth` on a full-document dict. Process each record on its `end` event, drop it, and
`break` after K records. Memory stays bounded only if finished work is discarded.

Threat model / landscape:
[`backlog/docs/streaming-memory-model-and-landscape.md`](backlog/docs/streaming-memory-model-and-landscape.md).

## Install

[PyPI](https://pypi.org/project/xml-iterator/) — package `xml-iterator`, import `xml_iterator`.

```bash
pip install xml-iterator
# or: uv pip install xml-iterator
```

From a clone: `make develop` (release extension; needed for honest benches/tests).

## Benchmarks

<!-- BEGIN BENCHMARKS -->
Release builds only (`make develop` / `make build`). Debug extensions are ~9× slower.

Numbers: **2026-07-17**. Source of truth: [`benchmark_data/benchmark_results.json`](benchmark_data/benchmark_results.json) (regenerate this section with `make readme-benchmarks`). Narrative: [`PERF_2026-07-17.md`](PERF_2026-07-17.md).

### Full-document dict — `xml_to_dict` vs `xmltodict.parse`

Same output shape on synthetic / SwissProt (attributes included; namespace prefixes stripped). Full-file tree build — fine for modest docs / parity; streaming is the large-file path.

**Synthetic**

| Elements | Size | `xml_iterator` | `xmltodict` | Speedup |
|----------|------|----------------|-------------|---------|
| 500 | 0.2 MB | 0.007s | 0.036s | 5.5× |
| 2,000 | 0.7 MB | 0.032s | 0.136s | 4.2× |
| 5,000 | 1.8 MB | 0.069s | 0.229s | 3.3× |

**Real files**

| Dataset | Size | `xml_iterator` | `xmltodict` | Speedup | Notes |
|---------|------|----------------|-------------|---------|-------|
| SwissProt | 110 MB | 2.573s | 13.342s | 5.19× | results identical |
| ESMA FIRDS | 441 MB | 8.451s | 54.379s | 6.43× | results differ (shape) |

Early stream exit (stop after 100,000 events on a 50,000-item file): **0.028s** vs full `xml_to_dict` **0.345s** (~12×). Any streaming parser gets this; not unique to this library.

### Stream backends — same event profile

Comparators in `xml_iterator.comparators`: `xml_iterator`, `et_iterparse`, `sax`, `lxml_iterparse`. All yield `(count, event, value)`. `make benchmark` / `make benchmark-all` time **every** backend (or record an explicit skip).

**Policy (one stream table per file):** full multi-backend drain if size ≤150 MB (e.g. SwissProt); else early exit first 1,000,000 events only (e.g. FIRDS). No redundant early+full on the same file. SAX is **N/A for early exit** (adapter materializes full parse first). SAX full drain skipped above 20 MB (RAM), not a capability gap.

**Synthetic** — 20,000 books, full drain (7.1 MB, 500,002 events)

| Backend | Time | Events | Rate | vs `xml_iterator` |
|---------|------|--------|------|-------------------|
| `xml_iterator` | 0.200s | 500,002 | 2.5M/s | 1.00× |
| `lxml_iterparse` | 0.466s | 500,002 | 1.1M/s | 2.33× slower |
| `sax` | 0.813s | 500,002 | 615k/s | 4.06× slower |
| `et_iterparse` | 1.036s | 500,002 | 482k/s | 5.18× slower |

**SwissProt** — full drain (110 MB, 7,967,906 events)

| Backend | Time | Events | Rate | vs `xml_iterator` |
|---------|------|--------|------|-------------------|
| `xml_iterator` | 2.088s | 7,967,906 | 3.8M/s | 1.00× |
| `lxml_iterparse` | 5.563s | 7,967,906 | 1.4M/s | 2.66× slower |
| `et_iterparse` | 7.496s | 7,967,906 | 1.1M/s | 3.59× slower |
| `sax` | skipped | — | — | skipped full drain >20MB (adapter buffers all events; RAM) |

**ESMA FIRDS** — early exit first 1,000,000 events (441 MB; full multi-backend drain >150 MB skipped)

| Backend | Time | Events | Rate | vs `xml_iterator` |
|---------|------|--------|------|-------------------|
| `xml_iterator` | 0.245s | 1,000,000 | 4.1M/s | 1.00× |
| `et_iterparse` | 0.777s | 1,000,000 | 1.3M/s | 3.17× slower |
| `lxml_iterparse` | 0.872s | 1,000,000 | 1.1M/s | 3.56× slower |
| `sax` | skipped | — | — | N/A early-exit (SAX adapter materializes full parse first) |

### Reproduce

```bash
make benchmark          # synthetic dict + stream + early-exit → JSON
make benchmark-all      # SwissProt + FIRDS → JSON
make show-benchmarks    # pretty-print last JSON (no rebuild)
make readme-benchmarks  # rewrite this section from JSON (no re-run)
```

Makefile installs `.[bench]` (`xmltodict`, `lxml`) and a **release** extension first. Committed snapshot: [`benchmark_data/benchmark_results.json`](benchmark_data/benchmark_results.json).
<!-- END BENCHMARKS -->

## Usage

```python
from xml_iterator.xml_iterator import iter_xml
from xml_iterator.core import xml_to_dict  # xml_iterator.xml_to_dict

# Streaming: records under open wrappers
records = 0
for count, event, value in iter_xml('file.xml'):
    if event == 'end' and value == 'FinInstrm':
        records += 1
        # handle; discard — do not accumulate under open parents
        if records >= 1000:
            break

# Full document dict — modest files / xmltodict parity only
data = xml_to_dict('small.xml')
```

Also: `get_edge_counts(path)`, opt-in attrs via `iter_xml(path, attributes=True)`.
Example: `examples/firds_shape_stream.py`. Sample event dump: `examples/simple.xml` +
`examples/example_xml_iter.py`.

**Limits:** file paths only (no pipes); namespace prefixes stripped; full-file
`xml_iterator.xml_to_dict` is not the multi-GB path.

**When to use something else:** stdlib `ET.iterparse` + `clear()`, [bigxml](https://github.com/Rogdham/bigxml),
or xmltodict `item_depth` callbacks — see landscape doc above.

## Develop

```bash
make develop          # release extension (default)
make develop-debug    # debug build (~9× slower)
pytest                # after: uv pip install -e ".[test]"
```

Changelog: [`CHANGELOG.md`](CHANGELOG.md).

### Release (one script → tag → CI → PyPI)

Package version lives **only** in `Cargo.toml` (pyproject is dynamic). A git tag `v*` must
match that version or CI uploads the wrong / already-published wheel.

```bash
# dry-run
python scripts/release.py patch --dry-run

# bump patch, edit Cargo + CHANGELOG, commit, annotated tag (local)
make release-patch
# or: python scripts/release.py patch -m "what changed" -m "another note"

# same + push main and tag → CI tests + maturin upload to PyPI
make release-push BUMP=patch
# or: python scripts/release.py 0.3.0 --push --gh-release

gh run watch   # wait for tag Release job
```

CI: [`.github/workflows/CI.yml`](.github/workflows/CI.yml) (`PYPI_API_TOKEN` secret).  
PyPI: https://pypi.org/project/xml-iterator/ · Releases: https://github.com/cottrell/xml_iterator/releases
