# Xml Iterator

An XML parser for Python with streaming iterator interface and protection against infinite depth attacks.

## Features

- **Streaming XML parsing** - processes XML without loading entire document into memory
- **Infinite depth protection** - iterator-based approach allows user-controlled limits
- **xmltodict-matching output** - `xml_to_dict()` matches xmltodict output including attributes
  (namespace prefixes are stripped; see Limitations)
- **Unicode support** - handles UTF-8 encoding correctly
- **Fails loudly** - malformed XML and undecodable text raise `ValueError` (no silent truncation)

## Performance

All numbers require a **release build** (`make develop` / `make build`); a debug build of the
extension is ~9x slower and was the cause of historically underwhelming benchmarks.

`xml_to_dict()` vs `xmltodict.parse()` (synthetic, 2026-07-17, now including attributes):

| Elements | File Size | xml_iterator | xmltodict | Speedup |
|----------|-----------|--------------|-----------|---------|
| 500 | 0.2 MB | 0.012s | 0.014s | 1.2x |
| 2,000 | 0.7 MB | 0.052s | 0.069s | 1.3x |
| 5,000 | 1.8 MB | 0.270s | 0.352s | 1.3x |

Full-file event streaming, SwissProt.xml (110 MB, 8.0M events):

| Approach | Time |
|----------|------|
| `iter_xml` full drain | 2.6s |
| `iter_xml(..., attributes=True)` (10.2M events) | 3.6s |
| stdlib `ET.iterparse` (start+end, `elem.clear()`) | 6.6s |
| Rust `get_edge_counts` (aggregation stays in Rust) | 1.3s |

On very large documents `xml_to_dict` is currently ~0.6x xmltodict (20.4s vs 12.9s on
SwissProt): the Python-side tree build dominates there; Rust-side dict building is the
planned fix.

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

# Streaming iteration
for count, event, value in iter_xml('file.xml'):
    print(f"{event}: {value}")
    if count > 1000:  # User-controlled limits
        break

# Convert to dictionary (xmltodict compatible)
data = xml_to_dict('file.xml', max_depth=100, max_events=10000)
```

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
