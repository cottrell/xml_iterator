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

Numbers: **2026-07-17**, machine `bleepblop`. Source of truth: [`benchmark_data/benchmark_results.json`](benchmark_data/benchmark_results.json) (regenerate this section with `make readme-benchmarks`). Narrative: [`PERF_2026-07-17.md`](PERF_2026-07-17.md).

### Full-document dict — `xml_to_dict` vs `xmltodict.parse`

Same output shape on synthetic / SwissProt (attributes included; namespace prefixes stripped). Full-file tree build — fine for modest docs / parity; streaming is the large-file path.

**Synthetic**

| Elements | Size | `xml_iterator` | `xmltodict` | Speedup |
|----------|------|----------------|-------------|---------|
| 500 | 0.2 MB | 0.004s | 0.016s | 4.4× |
| 2,000 | 0.7 MB | 0.012s | 0.066s | 5.5× |
| 5,000 | 1.8 MB | 0.032s | 0.155s | 4.9× |

**Real files**

| Dataset | Size | `xml_iterator` | `xmltodict` | Speedup | Notes |
|---------|------|----------------|-------------|---------|-------|
| SwissProt | 110 MB | 2.673s | 12.657s | 4.74× | results identical |
| ESMA FIRDS | 441 MB | 8.659s | 58.421s | 6.75× | results differ (shape) |

Early stream exit (stop after 1,000 events on a 10,000-item file): **0.0003s** vs full `xml_to_dict` **0.064s** (~229×). Any streaming parser gets this; not unique to this library.

### Stream backends — same event profile

Comparators in `xml_iterator.comparators`: `xml_iterator`, `et_iterparse`, `sax`, `lxml_iterparse`. All yield `(count, event, value)`. `make benchmark` / `make benchmark-all` time **every** backend (or record an explicit skip).

**SAX note:** the SAX adapter materializes the full parse into a list before iteration, so “first N events” still pays full-file cost. Prefer `xml_iterator` / `et` / `lxml` for true early exit. Full SAX drain is skipped above 20 MB.

**Synthetic** — 2,000 books, full drain (0.7 MB, 50,002 events)

| Backend | Time | Events | Rate | vs `xml_iterator` |
|---------|------|--------|------|-------------------|
| `xml_iterator` | 0.016s | 50,002 | 3.2M/s | 1.00× |
| `lxml_iterparse` | 0.032s | 50,002 | 1.5M/s | 2.06× slower |
| `sax` | 0.048s | 50,002 | 1.0M/s | 3.06× slower |
| `et_iterparse` | 0.053s | 50,002 | 940k/s | 3.38× slower |

**SwissProt** — full drain (110 MB, 7,967,906 events)

| Backend | Time | Events | Rate | vs `xml_iterator` |
|---------|------|--------|------|-------------------|
| `xml_iterator` | 2.229s | 7,967,906 | 3.6M/s | 1.00× |
| `lxml_iterparse` | 5.901s | 7,967,906 | 1.4M/s | 2.65× slower |
| `et_iterparse` | 8.325s | 7,967,906 | 957k/s | 3.74× slower |
| `sax` | skipped | — | — | full drain >20MB (SAX buffers all events) |

**SwissProt** — first 10 000 events (110 MB)

| Backend | Time | Events | Rate | vs `xml_iterator` |
|---------|------|--------|------|-------------------|
| `xml_iterator` | 0.003s | 10,000 | 3.7M/s | 1.00× |
| `lxml_iterparse` | 0.007s | 10,000 | 1.4M/s | 2.58× slower |
| `et_iterparse` | 0.011s | 10,000 | 926k/s | 4.04× slower |
| `sax` | 7.771s | 10,000 | 1k/s | 2904.35× slower |

**ESMA FIRDS** — first 10 000 events only (441 MB; full multi-backend drain capped at 150 MB)

| Backend | Time | Events | Rate | vs `xml_iterator` |
|---------|------|--------|------|-------------------|
| `xml_iterator` | 0.010s | 10,000 | 1.0M/s | 1.00× |
| `lxml_iterparse` | 0.009s | 10,000 | 1.1M/s | 1.11× faster |
| `et_iterparse` | 0.010s | 10,000 | 1.0M/s | 1.00× |
| `sax` | 26.062s | 10,000 | 384/s | 2612.00× slower |

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

### Release (git tag → CI → PyPI + GitHub)

Already wired: tag `v*` runs [`.github/workflows/CI.yml`](.github/workflows/CI.yml) (build/test, then
`maturin upload` using repo secret `PYPI_API_TOKEN`).

```bash
# 1. Bump Cargo.toml version, update CHANGELOG.md, commit, push main
# 2. Annotated tag + push (this publishes wheels to PyPI when CI is green)
git tag -a v0.2.1 -m "v0.2.1: short summary"
git push origin v0.2.1
gh run watch   # optional: wait for CI / Release job

# 3. GitHub Release page (notes only; packages already on PyPI from step 2)
gh release create v0.2.1 --title "v0.2.1" --notes-file CHANGELOG.md
# or click "Draft a release" on the tag in the GitHub UI
```

PyPI: https://pypi.org/project/xml-iterator/  
Releases: https://github.com/cottrell/xml_iterator/releases
