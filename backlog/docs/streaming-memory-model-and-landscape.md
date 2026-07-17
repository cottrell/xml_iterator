# Streaming memory model, FIRDS shape, and landscape

**Status:** reference / backlog context  
**Date:** 2026-07-17  
**Authors:** Grok (notes from discussion); problem framing from project origin (FIRDS-scale files)

Related: `REVIEW_2026-07-17.md`, `GROK_RESPONSE.md`, `PERF_2026-07-17.md`, task-1* correctness work.

---

## 1. The problem this library was actually built for

### Not primarily “infinite depth bombs”

Security-style “depth attack” language (billion-laughs-ish nesting, recursion limits) is real but **secondary**. The motivating data shape is closer to **breadth under open ancestors**:

```text
<root>                          ← opens near start of file
  <Hdr>...</Hdr>
  <Payload>
    <RefData>                   ← still open for almost the whole file
      <FinInstrm> ... </FinInstrm>   ← record 1  (complete here)
      <FinInstrm> ... </FinInstrm>   ← record 2
      ...
      <FinInstrm> ... </FinInstrm>   ← record N  (N can be huge / millions-scale)
    </RefData>                  ← closes near EOF
  </Payload>
</root>                         ← closes at EOF
```

FIRDS-like dumps (memory is approximate; names vary by feed) are typically:

- **Shallow-to-moderate nesting** (a handful of wrapper levels).
- **One (or a few) long lists** of almost-identical record elements deep under those wrappers.
- Outer tags **do not close until the file is finished**.

### What fails on that shape

| Approach | Failure mode |
|---|---|
| DOM / full tree (`ET.parse`, `lxml.parse`) | Holds entire document until parse completes. Outer element “owns” millions of children → RAM ~ file size (or worse). |
| Full `xmltodict.parse` (default) | Same: one giant dict; outer key not finished until EOF. |
| Building one dict for the whole file via streaming events (`xml_to_dict` without discard) | **Same memory problem** — streaming the *parser* does not help if the *consumer* accumulates everything under open parents. |
| Waiting for outer `end` to process children | You only finish after reading the whole file. Too late for “process records as they complete.” |

### What must work

**Yield or process each record when that record’s own `end` event fires**, while ancestors remain open.

```text
time →
  start root
  start Payload
  start RefData
  start FinInstrm … end FinInstrm   ← record 1 ready; root still open
  start FinInstrm … end FinInstrm   ← record 2 ready
  …
  end RefData
  end Payload
  end root
```

Requirements implied:

1. Event stream (or subtree callback) **does not wait** for outer close.
2. Memory stays O(depth + current record + whatever the user keeps), **not** O(file size), **if** the user drops finished records.
3. Early exit is allowed after K records without reading the rest of the file.
4. Optional: path/edge stats over structure without materializing values.

This is the real “memory-nice XML in Python” gap people hit: not “no C parser exists,” but **“I need record-at-a-time under a file-spanning wrapper without holding the wrapper’s children.”**

### Depth vs breadth (clarify project language)

| Concept | Meaning | FIRDS relevance |
|---|---|---|
| **Depth** | Nesting levels of open tags | Usually modest; recursive dict normalize can still explode if someone builds a pathological deep tree. |
| **Breadth / open parent** | Many siblings under a still-open parent | **Primary.** Millions of records under tags that close only at EOF. |
| **Early termination** | Stop iterating before EOF | Useful for sampling, tests, “first 10k events.” Any true stream gets this. |
| **Constant memory** | Only if consumer discards finished subtrees | Iterator alone is not enough; `xml_to_dict(full file)` reintroduces the problem. |

Docs that say only “infinite depth protection via streaming” undersell the real threat model. Prefer:

> **Open-ancestor streaming:** process complete child elements without waiting for outer wrappers that span the whole file; memory stays bounded if finished children are not retained.

---

## 2. How `xml_iterator` maps (honest)

| API | Fits FIRDS shape? | Notes |
|---|---|---|
| `iter_xml` | **Yes** | Emits start/end/text as file is read; record `end` fires while root open. User can break early. Memory: O(1) parser + Python event objects if user doesn’t accumulate. |
| `get_edge_counts` | Partial | Can scan structure; if it holds only path→count maps, fine. Must not panic on empty; must not require full DOM. |
| `xml_to_dict` (full file) | **No** for multi‑GB / millions of records | Rebuilds a whole tree → same class of OOM as xmltodict default. Fine for small files / tests / parity. |
| `xml_to_dict(..., max_events=N)` | Partial | Caps work; not a clean “per record” API. |
| `max_depth` | Wrong tool for FIRDS | Caps nesting, not “discard finished siblings under open parent.” Must not corrupt stack (see review fixes). |

**Design identity that matches origin story:**

- First-class: streaming events (and maybe “iter records under path X”).
- Second-class / small-file only: full-document dict conversion.
- Do not market full `xml_to_dict` as the FIRDS solution.

Possible future API (backlog idea, not committed):

```text
for record in iter_elements(path, tag="FinInstrm"):  # or path matcher
    process(record)   # subtree completed; ancestors still open; then drop
```

That is the ergonomics gap `iterparse` forces people to reinvent (and where bigxml / xmltodict `item_depth` live).

---

## 3. Landscape (what existed / exists)

Years-ago surprise (“no memory-nice Python XML”) was **half right**:

- **Engines always existed** (stdlib Expat/SAX, `ET.iterparse`, lxml.iterparse).
- **Discoverable, record-oriented APIs** were thin; default tutorials push full parse → OOM on FIRDS-scale files.
- `iterparse` only stays memory-safe if you **`elem.clear()`** (and often clear ancestors carefully). Easy to get wrong → still OOM with open parents retaining children.

### Engines (memory OK if used correctly)

| Tool | Role |
|---|---|
| `xml.etree.ElementTree.iterparse` | Stdlib stream; clear finished elems. |
| `lxml.etree.iterparse` | Faster C; same discipline. |
| `xml.sax` / `xml.parsers.expat` | Callback SAX; true streaming. |
| `xml.dom.pulldom` | Pull events; niche. |

### Dict / ergonomic layers

| Tool | Role |
|---|---|
| **xmltodict** default `parse` | Full tree — **not** for FIRDS-as-one-dict. |
| **xmltodict** `item_depth` + callback | Stream completed subtrees at a depth — right *shape* for record lists under wrappers. Past RAM bugs if parents accumulate; check current version. |
| **bigxml** ([Rogdham/bigxml](https://github.com/Rogdham/bigxml), PyPI) | Explicit “big files / streams, don’t DIY memory”; closest product cousin. Handler-based; pure Python; maintained into 2025. |
| **xml-stream**, **xmlstreamer** | Smaller streaming wrappers; less standard. |
| **xmlutils** (older) | Serial XML→CSV/SQL via iterparse. |

### Build vs buy (for this repo)

| Need | Prefer |
|---|---|
| Max speed, zero deps, FIRDS records | `ET.iterparse` + clear (or lxml) with explicit record tag |
| Maintained big-file library | Evaluate **bigxml** |
| Dict-shaped **per record** | xmltodict streaming **or** small helper on top of `iter_xml` |
| Path/edge counts, custom event loop, Rust experiments | This project |
| Full file as one dict | Only small files; not the mission |

**Still a niche for `xml_iterator`:** simple `(count, event, value)` stream with user-controlled stop; edge counts; optional Rust-side aggregation later. **Not a niche:** “faster full DOM than everyone else” or “xmltodict but for the entire FIRDS file in RAM.”

---

## 4. Implications for docs and backlog

### Docs should say

1. **Primary use case:** stream events / records under file-spanning wrappers (FIRDS-like).
2. **Memory contract:** parser is streaming; **user must not retain every finished child** if they want bounded RAM.
3. **`xml_to_dict`:** convenience / compatibility for modest documents — not the large-file path.
4. Retire or rephrase “infinite depth protection” as **open-ancestor streaming + optional early stop** (depth caps are a different, weaker tool).
5. Benchmark honestly vs `ET.iterparse` (and early-exit as a generic streaming property).

### Backlog-shaped work (ideas)

- [ ] **Threat-model doc pass** in README/AGENTS: open-parent breadth + diagram (this file can be linked).
- [ ] **Example:** “process first N `FinInstrm`-like records without loading file” using `iter_xml` (and/or iterparse comparison).
- [ ] **API spike (optional):** `iter_subtrees(path, tag=...)` or depth/path filter so Python never sees millions of irrelevant events (also a perf win vs per-event FFI).
- [ ] **Do not** optimize `xml_to_dict(full FIRDS)` as success metric.
- [ ] **Compare once** to bigxml + xmltodict `item_depth` on a FIRDS slice; record results under `benchmark_data/` or PERF notes.
- [ ] Adversarial test: synthetic file with shallow wrappers + M sibling records; assert (a) record ends appear before outer end, (b) processing with discard stays under a memory budget (or at least under a large bound), (c) early break after K records works.

### Acceptance sketch for a “FIRDS shape” regression

```text
XML: <r><list><item>i</item> × 100_000</list></r>
- iter_xml yields 100_000 item end events before list/r end
- consumer that counts items and retains nothing finishes without building a 100k-list in one parent dict
- break after 1000 item ends is allowed without reading entire file (event count / position check)
```

---

## 5. Correction log (review discussion)

Earlier review commentary focused a lot on:

- per-event FFI speed vs `ET.iterparse`
- silent errors, attributes, CDATA, `max_depth` corruption
- recursion in `_normalize_dict`

Those remain valid **engineering** issues. They must not redefine the product goal.

**Product goal restated:**

> Read huge, wrapper-heavy XML (many records under elements that stay open until EOF) with bounded memory and user-controlled termination — without requiring the outer element to close first.

Speed is secondary. Full-document dict parity is a side quest. Open-ancestor streaming is the core.

---

## 6. References (external)

- Python docs: `xml.etree.ElementTree.iterparse` — incremental parse; note tree still builds unless cleared.
- lxml: `etree.iterparse` performance notes.
- xmltodict: streaming mode (`item_depth`, callback) for large dumps.
- bigxml: https://github.com/Rogdham/bigxml — “iterparse is hard not to OOM.”
- ESMA FIRDS full dumps — multi-file ZIP XML; practical multi‑100MB+ inputs for this project’s benchmarks.
