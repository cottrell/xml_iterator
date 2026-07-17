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

## Benchmarks

Release builds only (`make develop` / `make build`). Debug extensions are ~9× slower.

Numbers below: **2026-07-17**, machine `bleepblop`. Raw JSON:
[`benchmark_data/benchmark_results.json`](benchmark_data/benchmark_results.json).
Narrative / before–after: [`PERF_2026-07-17.md`](PERF_2026-07-17.md).

### `xml_iterator.xml_to_dict` vs `xmltodict.parse`

Same output shape (attributes included; namespace prefixes stripped). Full-file dict rebuild —
for **modest** documents / parity, not multi-GB FIRDS-as-one-tree.

Synthetic (attrs, identical results):

| Elements | Size | `xml_iterator.xml_to_dict` | `xmltodict.parse` | Speedup |
|----------|------|----------------------------|-------------------|---------|
| 500 | 0.2 MB | 0.003s | 0.019s | 7.0× |
| 2,000 | 0.7 MB | 0.011s | 0.062s | 5.6× |
| 5,000 | 1.8 MB | 0.030s | 0.169s | 5.7× |

SwissProt (110 MB): **`xml_iterator.xml_to_dict` 3.0s** vs **`xmltodict.parse` 13.2s** (4.5×).

ESMA FIRDS (~441 MB full dict): **`xml_iterator.xml_to_dict` 72s** vs **`xmltodict.parse` 45s**
(slower — full tree still loses at this scale; use streaming).

### Streaming / other APIs (SwissProt 110 MB)

| Approach | Time |
|----------|------|
| `xml_iterator.iter_xml` full drain (8.0M events) | 2.6s |
| `xml_iterator.iter_xml(..., attributes=True)` (10.2M events) | 3.6s |
| stdlib `ET.iterparse` (start+end, `elem.clear()`) | 6.6s |
| `xml_iterator.get_edge_counts` (aggregation in Rust) | 1.3s |

Reproduce: `make benchmark` (synthetic), `make benchmark-real` (SwissProt),
`make benchmark-firds` / `make benchmark-all`. Needs `uv pip install -e ".[bench]"`.

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
