# Xml Iterator

A reasonably fast XML parser for Python with streaming iterator interface and protection against infinite depth attacks.

## Features

- **Streaming XML parsing** - processes XML without loading entire document into memory
- **Infinite depth protection** - iterator-based approach allows user-controlled limits
- **xmltodict compatibility** - `xml_to_dict()` function produces identical results to xmltodict library
- **High performance** - Rust implementation 1.2x faster than xmltodict, 734x faster for early termination
- **Unicode support** - handles UTF-8 encoding correctly

## Performance

Benchmarks comparing `xml_to_dict()` against `xmltodict.parse()`:

| Elements | File Size | xml_iterator | xmltodict | Speedup |
|----------|-----------|--------------|-----------|---------|
| 500 | 0.2 MB | 0.020s | 0.024s | 1.2x |
| 2,000 | 0.7 MB | 0.095s | 0.099s | 1.1x |
| 5,000 | 1.8 MB | 0.231s | 0.251s | 1.1x |

**Streaming advantage**: 734x faster when processing only first 1,000 events from large files.

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
pip install -e ".[test]"

# Run all tests
pytest

# Run specific test types
pytest tests/test_basic.py           # Core functionality
pytest tests/test_xmltodict.py       # xmltodict compatibility
pytest tests/test_performance.py    # Performance regression tests

# Run benchmarks (separate from tests)
make benchmark           # Synthetic data vs xmltodict
make benchmark-real      # Real-world ESMA FIRDS XML
```

The test suite includes:
- ✅ **Basic functionality tests** - streaming, encoding, deep nesting
- ✅ **xmltodict compatibility tests** - 100% exact result compatibility
- ✅ **Performance regression tests** - ensure no slowdowns

## Example Output

```python
In [1]: from xml_iterator.xml_iterator import get_edge_counts, iter_xml

In [2]: get_edge_counts('simple.xml')
xml_iterator::reading "simple.xml"
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
xml_iterator::reading "simple.xml"
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
