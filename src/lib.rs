use encoding_rs_io::DecodeReaderBytes;
use pyo3::exceptions::{PyOSError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};
use pyo3::IntoPyObjectExt;
use quick_xml::{events::Event, Decoder, Reader};
use std::{
    collections::{HashMap, VecDeque},
    error::Error,
    fs::File,
    io::{BufReader, Read, Seek, SeekFrom},
    str,
};

#[pymodule]
fn xml_iterator(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(iter_xml, m)?)?;
    m.add_function(wrap_pyfunction!(get_edge_counts, m)?)?;
    m.add_function(wrap_pyfunction!(xml_to_dict, m)?)?;
    Ok(())
}

#[pyfunction]
#[pyo3(signature = (path, attributes = false))]
fn iter_xml(path: &str, attributes: bool) -> PyResult<Py<PyAny>> {
    Python::attach(|py| -> PyResult<Py<PyAny>> {
        let iterator = get_xml_iterator(path, attributes).map_err(|e| {
            PyOSError::new_err(format!("Failed to open XML file: {}", e))
        })?;
        let myiter = PyXMLIterator {
            iter: std::sync::Mutex::new(Box::new(iterator)),
        };
        let bound = Bound::new(py, myiter)?;
        Ok(bound.into_any().unbind())
    })
}

#[pyfunction]
#[pyo3(signature = (path, n_max = None))]
fn get_edge_counts(path: &str, n_max: Option<u32>) -> PyResult<Py<PyAny>> {
    let iterator = get_xml_iterator(path, false).map_err(|e| {
        PyOSError::new_err(format!("Failed to open XML file: {}", e))
    })?;
    let counter = Python::attach(|py| {
        py.detach(|| -> Result<HashMap<Vec<String>, i32>, String> {
            let mut counter: HashMap<Vec<String>, i32> = HashMap::new();
            let mut tag_stack: Vec<String> = Vec::new();
            for item in iterator {
                let (count, event, payload) = item?;
                match event {
                    "start" => {
                        if let Payload::Str(value) = payload {
                            tag_stack.push(value);
                            *counter.entry(tag_stack.clone()).or_insert(0) += 1;
                        }
                    }
                    "empty" => {
                        if let Payload::Str(value) = payload {
                            let mut key = tag_stack.clone();
                            key.push(value);
                            *counter.entry(key).or_insert(0) += 1;
                        }
                    }
                    "end" => {
                        tag_stack.pop();
                    }
                    _ => {}
                }
                if let Some(x) = n_max {
                    if count > x {
                        break;
                    }
                }
            }
            Ok(counter)
        })
    })
    .map_err(PyValueError::new_err)?;
    Python::attach(|py| -> PyResult<Py<PyAny>> {
        let counter_out = PyDict::new(py);
        for (k, v) in counter.into_iter() {
            let k_tuple = PyTuple::new(py, k)?;
            counter_out.set_item(&k_tuple, v)?;
        }
        Ok(counter_out.into_any().unbind())
    })
}

#[pyfunction]
#[pyo3(signature = (path, max_depth = None, max_events = None))]
fn xml_to_dict(path: &str, max_depth: Option<usize>, max_events: Option<u64>) -> PyResult<Py<PyAny>> {
    Python::attach(|py| -> PyResult<Py<PyAny>> {
        let iterator = get_xml_iterator(path, true).map_err(|e| {
            PyOSError::new_err(format!("Failed to open XML file: {}", e))
        })?;

        let mut stack: Vec<Frame> = Vec::new();
        let mut pending_empty: Option<Frame> = None;
        let mut skipping: usize = 0;
        let mut event_count: u64 = 0;
        let mut root_tag: Option<String> = None;
        let mut root: Option<Py<PyAny>> = None;

        for item in iterator {
            let (_, event, payload) = item.map_err(PyValueError::new_err)?;
            event_count += 1;
            if let Some(me) = max_events {
                if event_count > me {
                    break;
                }
            }
            match event {
                "start" => {
                    if skipping > 0 {
                        skipping += 1;
                        continue;
                    }
                    if let Some(md) = max_depth {
                        if stack.len() >= md {
                            skipping = 1;
                            continue;
                        }
                    }
                    let tag = match payload {
                        Payload::Str(s) => s,
                        Payload::Pair(..) => unreachable!(),
                    };
                    flush_pending_empty(py, &mut pending_empty, &mut stack, &mut root_tag, &mut root)?;
                    stack.push(Frame { tag, dict: None, text: None });
                }
                "empty" => {
                    if skipping > 0 {
                        continue;
                    }
                    if let Some(md) = max_depth {
                        if stack.len() >= md {
                            continue;
                        }
                    }
                    let tag = match payload {
                        Payload::Str(s) => s,
                        Payload::Pair(..) => unreachable!(),
                    };
                    flush_pending_empty(py, &mut pending_empty, &mut stack, &mut root_tag, &mut root)?;
                    pending_empty = Some(Frame { tag, dict: None, text: None });
                }
                "attr" => {
                    if skipping > 0 {
                        continue;
                    }
                    let (name, value) = match payload {
                        Payload::Pair(n, v) => (n, v),
                        Payload::Str(..) => unreachable!(),
                    };
                    let key = format!("@{name}");
                    // attrs always precede children by construction (see queue_attributes).
                    if let Some(frame) = pending_empty.as_mut() {
                        attach_attr(py, frame, key, value)?;
                    } else if let Some(frame) = stack.last_mut() {
                        attach_attr(py, frame, key, value)?;
                    }
                }
                "text" => {
                    if skipping > 0 {
                        continue;
                    }
                    let text = match payload {
                        Payload::Str(s) => s,
                        Payload::Pair(..) => unreachable!(),
                    };
                    flush_pending_empty(py, &mut pending_empty, &mut stack, &mut root_tag, &mut root)?;
                    if let Some(frame) = stack.last_mut() {
                        match frame.text.as_mut() {
                            Some(t) => t.push_str(&text),
                            None => frame.text = Some(text),
                        }
                    }
                }
                "end" => {
                    if skipping > 0 {
                        skipping -= 1;
                        continue;
                    }
                    flush_pending_empty(py, &mut pending_empty, &mut stack, &mut root_tag, &mut root)?;
                    if let Some(frame) = stack.pop() {
                        let tag = frame.tag.clone();
                        let value = finalize(py, frame)?;
                        attach_or_root(py, &mut stack, &mut root_tag, &mut root, tag, value)?;
                    }
                }
                _ => {}
            }
        }

        // Covers both natural EOF (stack already empty, root already set via
        // the root's "end" event) and a max_events break mid-document.
        flush_pending_empty(py, &mut pending_empty, &mut stack, &mut root_tag, &mut root)?;
        while let Some(frame) = stack.pop() {
            let tag = frame.tag.clone();
            let value = finalize(py, frame)?;
            attach_or_root(py, &mut stack, &mut root_tag, &mut root, tag, value)?;
        }

        match (root_tag, root) {
            (Some(tag), Some(value)) => {
                let d = PyDict::new(py);
                d.set_item(tag, value)?;
                Ok(d.into_any().unbind())
            }
            _ => Ok(PyDict::new(py).into_any().unbind()),
        }
    })
}

struct Frame<'py> {
    tag: String,
    dict: Option<Bound<'py, PyDict>>,
    text: Option<String>,
}

fn attach_attr<'py>(py: Python<'py>, frame: &mut Frame<'py>, key: String, value: String) -> PyResult<()> {
    if frame.dict.is_none() {
        frame.dict = Some(PyDict::new(py));
    }
    frame.dict.as_ref().unwrap().set_item(key, value)?;
    Ok(())
}

fn finalize<'py>(py: Python<'py>, frame: Frame<'py>) -> PyResult<Py<PyAny>> {
    match (frame.dict, frame.text) {
        (Some(d), Some(t)) => {
            d.set_item("#text", t)?;
            Ok(d.into_any().unbind())
        }
        (Some(d), None) => Ok(d.into_any().unbind()),
        (None, Some(t)) => t.into_py_any(py),
        (None, None) => Ok(py.None()),
    }
}

fn attach<'py>(py: Python<'py>, parent: &mut Frame<'py>, tag: String, value: Py<PyAny>) -> PyResult<()> {
    if parent.dict.is_none() {
        parent.dict = Some(PyDict::new(py));
    }
    let dict = parent.dict.as_ref().unwrap();
    match dict.get_item(tag.as_str())? {
        None => {
            dict.set_item(tag, value)?;
        }
        Some(existing) => {
            if let Ok(list) = existing.cast::<PyList>() {
                list.append(value)?;
            } else {
                let newlist = PyList::new(py, [existing.unbind(), value])?;
                dict.set_item(tag, newlist)?;
            }
        }
    }
    Ok(())
}

fn flush_pending_empty<'py>(
    py: Python<'py>,
    pending_empty: &mut Option<Frame<'py>>,
    stack: &mut Vec<Frame<'py>>,
    root_tag: &mut Option<String>,
    root: &mut Option<Py<PyAny>>,
) -> PyResult<()> {
    if let Some(frame) = pending_empty.take() {
        let tag = frame.tag.clone();
        let value = finalize(py, frame)?;
        attach_or_root(py, stack, root_tag, root, tag, value)?;
    }
    Ok(())
}

fn attach_or_root<'py>(
    py: Python<'py>,
    stack: &mut Vec<Frame<'py>>,
    root_tag: &mut Option<String>,
    root: &mut Option<Py<PyAny>>,
    tag: String,
    value: Py<PyAny>,
) -> PyResult<()> {
    if let Some(parent) = stack.last_mut() {
        attach(py, parent, tag, value)
    } else {
        *root_tag = Some(tag);
        *root = Some(value);
        Ok(())
    }
}

enum Payload {
    Str(String),
    Pair(String, String),
}

type RawItem = (u32, &'static str, Payload);

#[pyclass]
struct PyXMLIterator {
    iter: std::sync::Mutex<Box<dyn Iterator<Item = Result<RawItem, String>> + Send>>,
}

#[pymethods]
impl PyXMLIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }
    fn __next__(slf: PyRefMut<'_, Self>) -> PyResult<Option<Py<PyAny>>> {
        let mut iter = slf.iter.lock().map_err(|_| PyValueError::new_err("mutex poisoned"))?;
        match iter.next() {
            None => Ok(None),
            Some(Err(msg)) => Err(PyValueError::new_err(msg)),
            Some(Ok((count, event, payload))) => Python::attach(|py| {
                let event_name = match event {
                    "start" => pyo3::intern!(py, "start"),
                    "end" => pyo3::intern!(py, "end"),
                    "empty" => pyo3::intern!(py, "empty"),
                    "text" => pyo3::intern!(py, "text"),
                    _ => pyo3::intern!(py, "attr"),
                };
                let value: Py<PyAny> = match payload {
                    Payload::Str(s) => s.into_py_any(py)?,
                    Payload::Pair(name, value) => (name, value).into_py_any(py)?,
                };
                let tuple = (count, event_name, value).into_py_any(py)?;
                Ok(Some(tuple))
            }),
        }
    }
}

struct XMLIterator {
    reader: Reader<BufReader<Box<dyn std::io::Read + Send>>>,
    count: u32,
    buf: Vec<u8>,
    with_attributes: bool,
    pending: VecDeque<RawItem>,
    open_depth: u32,
}

impl Iterator for XMLIterator {
    type Item = Result<RawItem, String>;
    fn next(&mut self) -> Option<Self::Item> {
        if let Some(item) = self.pending.pop_front() {
            return Some(Ok(item));
        }
        loop {
            self.buf.clear();
            let event = match self.reader.read_event_into(&mut self.buf) {
                Ok(event) => event,
                Err(e) => {
                    return Some(Err(format!(
                        "XML parse error at position {}: {}",
                        self.reader.buffer_position(),
                        e
                    )));
                }
            };
            match event {
                Event::Start(e) => {
                    let local_name = e.local_name();
                    let value = match self.reader.decoder().decode(local_name.into_inner()) {
                        Ok(v) => v.into_owned(),
                        Err(_) => return Some(Err("invalid encoding in tag name".into())),
                    };
                    let count = self.count;
                    self.count += 1;
                    self.open_depth += 1;
                    if self.with_attributes {
                        if let Err(msg) =
                            XMLIterator::queue_attributes(&mut self.pending, &mut self.count, &e, self.reader.decoder())
                        {
                            return Some(Err(msg));
                        }
                    }
                    return Some(Ok((count, "start", Payload::Str(value))));
                }
                Event::End(e) => {
                    let local_name = e.local_name();
                    let value = match self.reader.decoder().decode(local_name.into_inner()) {
                        Ok(v) => v.into_owned(),
                        Err(_) => return Some(Err("invalid encoding in tag name".into())),
                    };
                    let count = self.count;
                    self.count += 1;
                    self.open_depth -= 1;
                    return Some(Ok((count, "end", Payload::Str(value))));
                }
                Event::Empty(e) => {
                    let local_name = e.local_name();
                    let value = match self.reader.decoder().decode(local_name.into_inner()) {
                        Ok(v) => v.into_owned(),
                        Err(_) => return Some(Err("invalid encoding in tag name".into())),
                    };
                    let count = self.count;
                    self.count += 1;
                    if self.with_attributes {
                        if let Err(msg) =
                            XMLIterator::queue_attributes(&mut self.pending, &mut self.count, &e, self.reader.decoder())
                        {
                            return Some(Err(msg));
                        }
                    }
                    return Some(Ok((count, "empty", Payload::Str(value))));
                }
                Event::Text(e) => {
                    let decoded = match self.reader.decoder().decode(e.as_ref()) {
                        Ok(v) => v,
                        Err(err) => {
                            return Some(Err(format!("invalid text encoding: {}", err)));
                        }
                    };
                    let text = match quick_xml::escape::unescape(&decoded) {
                        Ok(text) => text.into_owned(),
                        Err(err) => {
                            return Some(Err(format!("invalid text content: {}", err)));
                        }
                    };
                    let trimmed = text.trim();
                    if trimmed.is_empty() {
                        continue;
                    }
                    let value = trimmed.to_string();
                    let count = self.count;
                    self.count += 1;
                    return Some(Ok((count, "text", Payload::Str(value))));
                }
                Event::CData(e) => {
                    let bytes = e.into_inner();
                    let text = match self.reader.decoder().decode(&bytes) {
                        Ok(text) => text.into_owned(),
                        Err(_) => return Some(Err("invalid encoding in CDATA".into())),
                    };
                    let trimmed = text.trim();
                    if trimmed.is_empty() {
                        continue;
                    }
                    let value = trimmed.to_string();
                    let count = self.count;
                    self.count += 1;
                    return Some(Ok((count, "text", Payload::Str(value))));
                }
                Event::Eof => {
                    if self.open_depth != 0 {
                        return Some(Err(format!(
                            "XML parse error: unexpected end of file with {} unclosed element(s)",
                            self.open_depth
                        )));
                    }
                    return None;
                }
                _ => continue,
            }
        }
    }
}

impl XMLIterator {
    fn queue_attributes(
        pending: &mut VecDeque<RawItem>,
        count: &mut u32,
        e: &quick_xml::events::BytesStart,
        decoder: Decoder,
    ) -> Result<(), String> {
        for attr in e.attributes() {
            let attr = attr.map_err(|err| format!("invalid attribute: {}", err))?;
            let name = decoder.decode(attr.key.local_name().into_inner())
                .map_err(|_| "invalid UTF-8 in attribute name".to_string())?
                .into_owned();
            let value = attr
                .decode_and_unescape_value(decoder)
                .map_err(|err| format!("invalid attribute value: {}", err))?
                .into_owned();
            let this_count = *count;
            *count += 1;
            pending.push_back((this_count, "attr", Payload::Pair(name, value)));
        }
        Ok(())
    }
}

fn get_xml_iterator(path: &str, with_attributes: bool) -> Result<XMLIterator, Box<dyn Error>> {
    let mut fin = File::open(path)?;
    // quick-xml cannot parse UTF-16 (its encoding feature covers only ASCII-compatible
    // encodings), so UTF-16-BOM files are transcoded to UTF-8. The XML declaration must
    // then be stripped: it may still say encoding="UTF-16", which would desync quick-xml's
    // decoder from the transcoded stream. All other files go to quick-xml raw, which
    // honors declared ASCII-compatible encodings (e.g. ISO-8859-1) itself.
    let mut bom = [0u8; 2];
    let bytes_read = fin.read(&mut bom)?;
    fin.seek(SeekFrom::Start(0))?;
    let utf16_bom = bytes_read >= 2 && (bom == [0xFE, 0xFF] || bom == [0xFF, 0xFE]);
    let reader_input: Box<dyn std::io::Read + Send> = if utf16_bom {
        let mut decoded = DecodeReaderBytes::new(fin);
        let mut head = Vec::with_capacity(4096);
        (&mut decoded).take(4096).read_to_end(&mut head)?;
        if head.starts_with(b"<?xml") {
            if let Some(pos) = head.windows(2).position(|w| w == b"?>") {
                head.drain(..pos + 2);
            }
        }
        Box::new(std::io::Cursor::new(head).chain(decoded))
    } else {
        Box::new(fin)
    };
    let bufreader = BufReader::new(reader_input);
    let reader = Reader::from_reader(bufreader);
    let reader_iter = XMLIterator {
        reader,
        count: 0,
        buf: Vec::new(),
        with_attributes,
        pending: VecDeque::new(),
        open_depth: 0,
    };
    Ok(reader_iter)
}
