# CLAUDE.md - AI Context for xml_iterator

## Project Overview

Fast XML parser with streaming iterator interface, built in Rust with Python bindings.
Primary goal: defeat the **infinite depth attack** (content under outer elements that stay open
until late/EOF — FIRDS-like). See `backlog/docs/streaming-memory-model-and-landscape.md`.

## Architecture

```
xml_iterator/
├── src/lib.rs                 # Rust core: XMLIterator + Python bindings  
├── xml_iterator/core.py       # Python utilities: xml_to_dict, get_edge_counts
├── tests/                     # Comprehensive pytest suite
└── benchmark*.py              # Performance testing vs xmltodict
```

## Core Components

### Rust Implementation (`src/lib.rs`)
- **XMLIterator**: Streaming XML parser using quick-xml
- **Events**: `start`, `end`, `text`, `empty` (self-closing tags), `attr` (opt-in)
- **Python bindings**: PyO3 integration
- **Protection**: No depth limits - user controls via early termination
- **Errors**: malformed XML and undecodable text raise `ValueError`, not silent truncation

### Python API
- **`iter_xml(path, attributes=False)`**: Stream events `(count, event, value)`; with
  `attributes=True` also yields `('attr', (name, value))` events
- **`xml_to_dict(path)`**: Full-document dict (xmltodict-compatible). Modest files / parity only —
  not the multi-GB FIRDS path (rebuilds the tree → loses to infinite depth at that scale)
- **`get_edge_counts(path)`**: Count tag hierarchies

## Key Features

✅ **Streaming under open ancestors** - child `end` while wrappers stay open (FIRDS shape)
✅ **Matches xmltodict output** - including attributes (namespace prefixes are stripped; see limitations)
✅ **Early-termination streaming** - stopping early avoids a full-document parse, a property of any streaming parser, not unique to this library
✅ **Bounded memory if work is discarded** - stream alone is not enough if every child is kept under open parents
✅ **Real-world tested** - handles 300MB+ ESMA FIRDS XML files via streaming
✅ **Fails loudly** - malformed XML and undecodable text raise `ValueError` (no silent truncation)

## Performance Characteristics

IMPORTANT: always benchmark a **release** build (`make develop`); debug builds are ~9x slower
and historically poisoned this project's numbers.

Release build, 2026-07-17 (see PERF_2026-07-17.md for the full story):

| Scenario | xml_iterator | baseline | Ratio |
|----------|-------------|----------|-------|
| xml_to_dict (Rust-built as of TASK-2), synthetic 5000 items (1.8 MB) | 0.030s | xmltodict 0.169s | 5.7x faster |
| xml_to_dict, SwissProt 110 MB (results identical) | 3.0s | xmltodict 13.2s | 4.5x faster |
| iter_xml full drain, SwissProt (8.0M events) | 2.6s | ET.iterparse 6.6s | 2.5x faster |
| Rust get_edge_counts, SwissProt | 1.3s | - | aggregation stays in Rust |
| Early termination (stop at 1000 events) | 0.001s | N/A | early exit avoids full parse - any streaming parser gets this |

Before-today (v0.1.4) baseline for the same scenarios: xml_to_dict 1.1x vs xmltodict and
SwissProt 11.6s (attribute-less, debug builds); iter_xml drain 20.5s (debug). See
PERF_2026-07-17.md.

## Development Workflow

```bash
# Build and install
make develop

# Run tests  
make test                # All tests
make test-fast          # Skip slow tests

# Run benchmarks
make benchmark          # Synthetic data vs xmltodict
make benchmark-real     # Real-world SwissProt XML data
make benchmark-firds    # Real ESMA FIRDS data (downloads 17MB)
make benchmark-all      # Run both real-world benchmarks

# Test specific components
pytest tests/test_basic.py        # Core functionality
pytest tests/test_xmltodict.py    # Compatibility  
pytest tests/test_performance.py  # Regression tests
```

## Project Status

- **Core functionality**: streaming iterator, xmltodict-matching dict conversion, edge counting
- **Tested**: synthetic data, real-world XML files, adversarial/edge cases
- **Benchmarked**: performance measured vs xmltodict and stdlib `ET.iterparse`

## Files of Interest

- **`src/lib.rs`**: Main Rust implementation
- **`xml_iterator/core.py`**: Python utilities and xml_to_dict
- **`tests/test_xmltodict.py`**: Compatibility verification  
- **`benchmark_real_world.py`**: Real-world performance testing
- **`benchmark.py`**: Synthetic benchmarks

## Known Limitations

- **Namespace prefixes stripped**: only local tag/attribute names are kept
- **Single file input**: No streaming from network/pipes (file paths only)
- **Python-only bindings**: No other language bindings yet

## Infinite Depth Attack / Protection

**Definition (project sense):** useful content sits under outer elements that do not close until
much later (often EOF). Tree/DOM must wait for outer close or retain the open tree. FIRDS dumps
are the concrete instance: wrappers open near the start, millions of records at that depth,
outers close at EOF.

```text
<root> <Payload> <RefData>          ← open almost whole file
  <FinInstrm>...</FinInstrm>        ← record complete; outers still open
  ...
</RefData></Payload></root>         ← close near EOF
```

**Protection:** stream events at depth under open outers; process on child `end`; user discards
finished work and may early-stop. **Not** primarily `max_depth` caps (those are nesting/work
limits). Full `xml_to_dict` is modest files / parity only.

Regression: `tests/test_firds_shape.py`. Example: `examples/firds_shape_stream.py`.

## Dependencies

- **Rust**: quick-xml, pyo3, encoding_rs_io
- **Python**: Standard library only (tests require pytest, xmltodict)
- **Build**: maturin for Python extension compilation

## Testing Philosophy

- **Exact compatibility**: matches xmltodict output including attributes
- **Real-world data**: ESMA FIRDS regulatory XML files  
- **Performance regression**: Ensure no slowdowns
- **Fail loudly**: malformed XML and undecodable text raise `ValueError`, no silent truncation

