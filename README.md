# Xml Iterator

An XML parser for Python with a streaming iterator interface. Primary goal: defeat the
**infinite depth attack** on large dumps where useful content sits under outer elements that
stay open until late/EOF (FIRDS-like shape).

Full threat model and landscape notes:
[`backlog/docs/streaming-memory-model-and-landscape.md`](backlog/docs/streaming-memory-model-and-landscape.md).

## Infinite depth attack

Useful records sit **under open outer elements that do not close until much later** (often EOF).
A tree/DOM consumer must wait for those outers to close or retain the whole open tree (memory
grows with the file). Streaming yields each child when *it* ends, while ancestors remain open.

```text
<root>                              ← opens near start
  <Hdr>...</Hdr>
  <Payload>
    <RefData>                       ← open for almost the whole file
      <FinInstrm> ... </FinInstrm>  ← record 1 complete (outers still open)
      <FinInstrm> ... </FinInstrm>  ← record 2
      ...
    </RefData>                      ← closes near EOF
  </Payload>
</root>
```

**Protection** is streaming at depth under open outers plus **user discard / early stop** — not
primarily `max_depth` caps. Process each record on its `end` event, drop it, and optionally
`break` after K records without finishing the file. Memory stays bounded only if finished work
is discarded (keeping every child under open parents still OOMs).

`max_depth` / `max_events` on `xml_to_dict` are weaker knobs (nesting/work caps). They are not
the infinite-depth protection mechanism.

## Features

- **Streaming XML parsing** - events as tags open/close; no full DOM required
- **Infinite depth protection** - complete inner elements under open wrappers; user-controlled
  early stop (see above)
- **xmltodict-matching output** - `xml_to_dict()` matches xmltodict for **modest files / parity**
  (namespace prefixes are stripped; see Limitations). **Not** the multi-GB FIRDS path — a full
  `xml_to_dict` rebuilds the tree and loses to infinite depth at that scale
- **Encoding support** - UTF-8 (with or without BOM), UTF-16 with BOM, and declared
  ASCII-compatible encodings (e.g. ISO-8859-1); undecodable input raises `ValueError`
- **Fails loudly** - malformed XML and undecodable text raise `ValueError` (no silent truncation)

## Performance

All numbers require a **release build** (`make develop` / `make build`); a debug build of the
extension is ~9x slower and was the cause of historically underwhelming benchmarks.

`xml_to_dict()` (built in Rust as of v0.2.0) vs `xmltodict.parse()` (synthetic, 2026-07-17,
including attributes; output verified identical):

| Elements | File Size | xml_iterator | xmltodict | Speedup |
|----------|-----------|--------------|-----------|---------|
| 500 | 0.2 MB | 0.003s | 0.019s | 7.0x |
| 2,000 | 0.7 MB | 0.011s | 0.062s | 5.6x |
| 5,000 | 1.8 MB | 0.030s | 0.169s | 5.7x |

SwissProt.xml (110 MB, 8.0M events), release build:

| Approach | Time |
|----------|------|
| `xml_to_dict` (dict built in Rust, results identical to xmltodict) | 3.0s |
| `xmltodict.parse` | 13.2s |
| `iter_xml` full drain | 2.6s |
| `iter_xml(..., attributes=True)` (10.2M events) | 3.6s |
| stdlib `ET.iterparse` (start+end, `elem.clear()`) | 6.6s |
| Rust `get_edge_counts` (aggregation stays in Rust) | 1.3s |

### Improvement over v0.1.4 (before 2026-07-17)

| Metric | before (v0.1.4) | now (v0.2.0) | change |
|--------|-----------------|--------------|--------|
| `xml_to_dict` vs xmltodict, synthetic 5000 | 1.1x faster | 5.7x faster | dict built in Rust |
| `xml_to_dict`, SwissProt 110 MB | 11.6s (no attributes) | 3.0s (with attributes) | ~3.9x, doing strictly more work |
| `iter_xml` full drain, SwissProt | 20.5s (debug build) | 2.6s | ~7.9x (release + buffer reuse/interning) |
| vs stdlib `ET.iterparse` (full drain) | 3.1x slower | 2.5x faster | debug-build discovery |
| Correctness | silent truncation, panics on `<a/>`, attrs dropped | fails loudly, xmltodict parity incl. attributes | see Changes in 0.2.0 |

**Early-termination advantage**: stopping after the first 1,000 events of a large file is far
cheaper than a full parse - this is a general property of streaming iteration (any streaming
parser, including stdlib's `ET.iterparse`, gets it), not something unique to this library.

Run benchmarks yourself:
- `make benchmark` - Synthetic data comparison vs xmltodict
- `make benchmark-real` - Real-world ESMA FIRDS XML file (downloads ~100MB)

## Usage

```python
from xml_iterator.xml_iterator import iter_xml
from xml_iterator.core import xml_to_dict

# Streaming: process records under open wrappers (FIRDS-like)
records = 0
for count, event, value in iter_xml('file.xml'):
    if event == 'end' and value == 'FinInstrm':
        records += 1
        # handle this record; discard — do not accumulate under open parents
        if records >= 1000:  # early stop without waiting for outer close
            break

# Full document dict — modest files / xmltodict parity only (not multi-GB FIRDS)
data = xml_to_dict('small.xml')
```

See `examples/firds_shape_stream.py` for a synthetic wrapper+records example.

## Testing

Run the test suite with pytest:

```bash
# Install test dependencies
uv pip install -e ".[test]"

# Run all tests
pytest

# Run specific test types
pytest tests/test_basic.py           # Core functionality
pytest tests/test_xmltodict.py       # xmltodict compatibility
pytest tests/test_performance.py    # Performance regression tests

# Run benchmarks (separate from tests)
make benchmark           # Synthetic data vs xmltodict
make benchmark-real      # Real-world SwissProt XML
make benchmark-firds     # Real-world ESMA FIRDS XML (downloads 17MB)
make benchmark-all       # Run both real-world benchmarks
```

The test suite includes:
- **Basic functionality tests** - streaming, encoding, deep nesting
- **FIRDS-shape tests** - records under open wrappers; early break (`tests/test_firds_shape.py`)
- **xmltodict compatibility tests** - exact result compatibility including attributes
- **Adversarial tests** - malformed XML, encodings, CDATA, attributes, max_depth, deep nesting
- **Performance regression tests** - ensure no slowdowns

## Changes in 0.2.0

- Malformed XML and undecodable text now raise `ValueError` instead of silently truncating the
  stream or dropping text.
- Attribute events are opt-in: `iter_xml(path, attributes=True)` yields `('attr', (name, value))`
  events; the default (`attributes=False`) is unchanged from before.
- `xml_to_dict` now includes attributes (as `@name` keys) and matches `xmltodict.parse` output.
- CDATA sections are now yielded as `text` events instead of being silently dropped.
- Self-closing tags (`<tag/>`) are now counted correctly by both `get_edge_counts`
  implementations (Rust previously panicked; Python previously undercounted).
- `xml_to_dict(max_depth=...)` no longer strands the parser stack and drops sibling elements.
- `xml_to_dict` uses an iterative (non-recursive) normalization pass, so it no longer hits
  Python's recursion limit on deeply nested documents.

## Limitations

- Namespace prefixes are stripped from tag and attribute names (only local names are kept).
- Single file input - no streaming from network/pipes (file paths only).
- Full-file `xml_to_dict` is for modest documents and compatibility tests, not large FIRDS-as-one-tree loads.

## Related tools (landscape)

| Need | Prefer |
|------|--------|
| Records under open wrappers, stdlib | `ET.iterparse` + `elem.clear()` (or lxml) |
| Maintained big-file streaming library | [bigxml](https://github.com/Rogdham/bigxml) |
| Dict-shaped subtrees at a depth | xmltodict `item_depth` + callback |
| Event tuples / edge counts / this project | `iter_xml`, `get_edge_counts` |

Details: [`backlog/docs/streaming-memory-model-and-landscape.md`](backlog/docs/streaming-memory-model-and-landscape.md).

## Example Output

```python
In [1]: from xml_iterator.xml_iterator import get_edge_counts, iter_xml

In [2]: get_edge_counts('simple.xml')
Out[2]:
{('breakfast_menu', 'food', 'price'): 5,
 ('breakfast_menu', 'food', 'description'): 5,
 ('breakfast_menu', 'food'): 5,
 ('breakfast_menu', 'food', 'calories'): 5,
 ('breakfast_menu',): 1,
 ('breakfast_menu', 'food', 'name'): 5}

In [3]: for x in iter_xml('simple.xml'):
   ...:     print(x)
   ...:
(0, 'start', 'breakfast_menu')
(1, 'start', 'food')
(2, 'start', 'name')
(3, 'text', 'Belgian Waffles')
(4, 'end', 'name')
(5, 'start', 'price')
(6, 'text', '$5.95')
(7, 'end', 'price')
(8, 'start', 'description')
(9, 'text', 'Two of our famous Belgian Waffles with plenty of real maple syrup')
(10, 'end', 'description')
(11, 'start', 'calories')
(12, 'text', '650')
(13, 'end', 'calories')
(14, 'end', 'food')
(15, 'start', 'food')
(16, 'start', 'name')
(17, 'text', 'Strawberry Belgian Waffles')
(18, 'end', 'name')
(19, 'start', 'price')
(20, 'text', '$7.95')
(21, 'end', 'price')
(22, 'start', 'description')
(23, 'text', 'Light Belgian waffles covered with strawberries and whipped cream')
(24, 'end', 'description')
(25, 'start', 'calories')
(26, 'text', '900')
(27, 'end', 'calories')
(28, 'end', 'food')
(29, 'start', 'food')
(30, 'start', 'name')
(31, 'text', 'Berry-Berry Belgian Waffles')
(32, 'end', 'name')
(33, 'start', 'price')
(34, 'text', '$8.95')
(35, 'end', 'price')
(36, 'start', 'description')
(37, 'text', 'Light Belgian waffles covered with an assortment of fresh berries and whipped cream')
(38, 'end', 'description')
(39, 'start', 'calories')
(40, 'text', '900')
(41, 'end', 'calories')
(42, 'end', 'food')
(43, 'start', 'food')
(44, 'start', 'name')
(45, 'text', 'French Toast')
(46, 'end', 'name')
(47, 'start', 'price')
(48, 'text', '$4.50')
(49, 'end', 'price')
(50, 'start', 'description')
(51, 'text', 'Thick slices made from our homemade sourdough bread')
(52, 'end', 'description')
(53, 'start', 'calories')
(54, 'text', '600')
(55, 'end', 'calories')
(56, 'end', 'food')
(57, 'start', 'food')
(58, 'start', 'name')
(59, 'text', 'Homestyle Breakfast')
(60, 'end', 'name')
(61, 'start', 'price')
(62, 'text', '$6.95')
(63, 'end', 'price')
(64, 'start', 'description')
(65, 'text', 'Two eggs, bacon or sausage, toast, and our ever-popular hash browns')
(66, 'end', 'description')
(67, 'start', 'calories')
(68, 'text', '950')
(69, 'end', 'calories')
(70, 'end', 'food')
(71, 'end', 'breakfast_menu')
```
