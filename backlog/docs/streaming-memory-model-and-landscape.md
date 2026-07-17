# Infinite depth attack, FIRDS, and landscape

**Status:** reference / backlog context  
**Date:** 2026-07-17 (corrected same day)  
**Related:** `REVIEW_2026-07-17.md`, `GROK_RESPONSE.md`, `PERF_2026-07-17.md`, task-1*, task-4

---

## 1. Infinite depth attack (the problem this library is for)

### Definition (project sense)

An **infinite depth attack** is any situation where useful content sits **under open outer elements that do not close until much later** (often EOF), so that a tree/DOM-style consumer must either:

1. **Wait for the outer element to close** before the parent node is “complete” → effectively requires reading the rest of the file first, or
2. **Retain the entire open spine and everything hung off it** until those closes arrive → memory grows with the document (often ~ file size or worse), or
3. **Recurse / stack with the nesting** in a way that blows up when depth is large or when the logical tree under open nodes is huge.

Streaming defeats it: **emit events as tags open and close; a child can be fully processed on its own `end` while ancestors are still open.** Depth of the open stack can stay open for the whole file; the user controls how much of the tree they keep.

This is **not** a rebrand of “breadth vs depth.” The name is **infinite depth**: you are at depth under wrappers for an effectively unbounded amount of content / time until outers close. Protection is the streaming design (plus user-controlled early stop), not a hard `max_depth` cap.

### Concrete instance: FIRDS-like dumps

```text
<root>                              ← opens near start
  <Hdr>...</Hdr>
  <Payload>
    <RefData>                       ← open for almost the whole file
      <FinInstrm> ... </FinInstrm>  ← record 1 complete here (outers still open)
      <FinInstrm> ... </FinInstrm>  ← record 2
      ...
      <FinInstrm> ... </FinInstrm>  ← record N (N can be huge / millions-scale)
    </RefData>                      ← closes near EOF
  </Payload>
</root>                             ← closes at EOF
```

Typical shape:

- Nesting: wrappers around wrappers, then a long list of records **at that depth**.
- Outers **do not close until the file is finished**.
- You must read records **without** requiring those outside elements to close by reading the entire file.

### What fails (loses to infinite depth)

| Approach | Failure |
|---|---|
| DOM / full tree (`ET.parse`, `lxml.parse`) | Outer node incomplete until EOF; holds millions of children. |
| Full `xmltodict.parse` (default) | Same: one giant dict keyed under still-open structure. |
| Full-file `xml_to_dict` over a stream | Parser may stream; **consumer rebuilds the whole tree** → same attack succeeds. |
| “I’ll process children when parent ends” | Parent ends only after all records → whole file first. |
| Recursive full-tree normalize on huge/deep trees | Stack / RecursionError (secondary, real for dict builder). |

### What works

```text
time →
  start root
  start Payload
  start RefData          ← stay open…
  start FinInstrm … end FinInstrm   ← record 1 done; still at depth under RefData
  start FinInstrm … end FinInstrm   ← record 2 done
  …
  end RefData
  end Payload
  end root
```

Requirements:

1. Events (or completed subtrees) **do not wait** on outer close.
2. Memory is O(open depth + current record + what the user keeps), not O(file), **if** finished records are dropped.
3. Early exit after K records without finishing the file.
4. Optional: path/edge stats without materializing values.

`max_depth` as “skip nesting levels” is a **different**, weaker knob. It is not the infinite-depth protection mechanism. Protection is: **stream at whatever depth you are, complete inner elements, don’t force outer close first.**

---

## 2. How `xml_iterator` maps

| API | Defeats infinite depth? | Notes |
|---|---|---|
| `iter_xml` | **Yes** | Child `end` while ancestors open; user can break. Bounded RAM if user doesn’t accumulate. |
| `get_edge_counts` | Yes for structure scan | Path→count only; must handle `empty`; no full DOM. |
| `xml_to_dict` (full file) | **No** at FIRDS scale | Rebuilds tree → attack succeeds. OK for small files / tests / xmltodict-ish parity. |
| `xml_to_dict(..., max_events=N)` | Partial | Caps work; not “per record at depth.” |
| `max_depth` | Not the protection | Nesting cap; must not corrupt stack if kept. |

**Identity:**

- First-class: streaming events under open ancestors at arbitrary depth.
- Second-class: full-document dict conversion (small files).
- Do not market full `xml_to_dict` as the FIRDS / infinite-depth solution.

Possible future API:

```text
for record in iter_elements(..., tag="FinInstrm"):
    process(record)   # complete at this depth; drop; outers still open
```

---

## 3. Landscape

Years-ago gap: **memory-nice handling of infinite-depth / file-spanning wrappers** was hard to find as a clear product, even though engines existed.

### Engines (OK if used correctly)

| Tool | Role |
|---|---|
| `xml.etree.ElementTree.iterparse` | Stream; must `clear()` finished elems or open parents retain children → OOM. |
| `lxml.etree.iterparse` | Same discipline; usually faster. |
| `xml.sax` / Expat | Callback stream; true streaming. |
| `xml.dom.pulldom` | Pull events; niche. |

### Layers

| Tool | Role |
|---|---|
| **xmltodict** default | Full tree — loses to infinite depth on large dumps. |
| **xmltodict** `item_depth` + callback | Complete subtrees at a depth without full document dict — right *shape*. Check current RAM behavior. |
| **bigxml** | Big files/streams; “iterparse easy to OOM.” Closest product cousin. |
| **xml-stream**, **xmlstreamer**, **xmlutils** | Smaller / older streaming helpers. |

### Build vs buy

| Need | Prefer |
|---|---|
| Speed, zero deps, records under open wrappers | `ET.iterparse` + clear (or lxml) |
| Maintained big-file library | Evaluate **bigxml** |
| Dict-shaped **per record** at depth | xmltodict streaming or helper on `iter_xml` |
| Event tuples, edge counts, Rust experiments | This project |
| Full file as one dict | Small files only |

---

## 4. Docs and backlog implications

### Docs should say

1. **Primary threat model:** infinite depth attack — content under outers that stay open until late/EOF (FIRDS-like).
2. **Protection:** streaming iterator; process on child `end`; user drops finished work; optional early stop.
3. **Memory contract:** stream is not enough if the consumer keeps every child under open parents.
4. **`xml_to_dict`:** modest documents / compatibility — not the large-file infinite-depth path.
5. Benchmark vs `ET.iterparse`; early-exit is a property of streaming generally.
6. Keep the name **infinite depth attack / protection**; do not replace it with unrelated marketing.

### Work ideas

- [ ] README/AGENTS: define infinite depth attack with FIRDS diagram; link this doc.
- [ ] Example: N records under open wrappers without loading whole file.
- [ ] Optional API: iter completed elements at path/tag (depth-aware record stream).
- [ ] Do not treat `xml_to_dict(full FIRDS)` as success.
- [ ] Compare once to bigxml + xmltodict `item_depth` on a FIRDS slice.
- [ ] Regression: sibling records under wrappers; child ends before outer ends; early break works.

### Acceptance sketch

```text
XML: <r><list><item>…</item> × 100_000</list></r>
- 100_000 item end events before list/r end  (infinite depth: still inside open outers)
- consumer that discards items does not build a 100k parent list
- break after 1000 item ends without reading entire file
```

---

## 5. Notes from review discussion (what not to confuse)

Engineering issues (silent EOF, attributes, CDATA, panics, FFI cost, recursive normalize) are real and separate.

They do **not** redefine the product goal.

**Product goal:**

> Defeat the infinite depth attack: stream XML so complete inner elements can be handled at depth under open outer elements that may span the whole file — bounded memory if finished work is discarded; no requirement to close outers first.

Speed secondary. Full-document dict parity is a side quest.

### Terminology mistake (2026-07-17)

An intermediate draft of this doc wrongly treated “infinite depth” as mere security recursion bombs and tried to rename the problem “open-ancestor breadth.” **That was a misunderstanding of the project’s threat model.** The FIRDS case *is* the infinite depth attack. Corrected above.

---

## 6. References

- Project AGENTS/CLAUDE: infinite depth protection via streaming.
- Python: `xml.etree.ElementTree.iterparse` (tree still grows unless cleared).
- lxml iterparse notes.
- xmltodict streaming (`item_depth`).
- bigxml: https://github.com/Rogdham/bigxml
- ESMA FIRDS full dumps — multi-100MB+ practical inputs.
