use encoding_rs_io::DecodeReaderBytes;
use pyo3::exceptions::{PyIOError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};
use quick_xml::{events::Event, Reader};
use std::{
    collections::{HashMap, VecDeque},
    error::Error,
    fs::File,
    io::BufReader,
    str,
};

#[pymodule]
fn xml_iterator(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(iter_xml, m)?)?;
    m.add_function(wrap_pyfunction!(get_edge_counts, m)?)?;
    Ok(())
}

#[pyfunction(attributes = "false")]
fn iter_xml(path: &str, attributes: bool) -> PyResult<PyObject> {
    Python::with_gil(|py| -> PyResult<PyObject> {
        let iterator = get_xml_iterator(path, attributes).map_err(|e| {
            PyIOError::new_err(format!("Failed to open XML file: {}", e))
        })?;
        let myiter = PyXMLIterator {
            iter: Box::new(iterator),
        };
        Ok(myiter.into_py(py))
    })
}

#[pyfunction]
fn get_edge_counts(path: &str, n_max: Option<u32>) -> PyResult<PyObject> {
    let iterator = get_xml_iterator(path, false).map_err(|e| {
        PyIOError::new_err(format!("Failed to open XML file: {}", e))
    })?;
    let counter = Python::with_gil(|py| {
        py.allow_threads(|| -> Result<HashMap<Vec<String>, i32>, String> {
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
    Python::with_gil(|py| -> PyResult<PyObject> {
        let counter_out = PyDict::new(py);
        for (k, v) in counter.into_iter() {
            let k = PyTuple::new(py, k);
            let _ = counter_out.set_item(k, v);
        }
        Ok(counter_out.into_py(py))
    })
}

enum Payload {
    Str(String),
    Pair(String, String),
}

type RawItem = (u32, &'static str, Payload);

#[pyclass]
struct PyXMLIterator {
    iter: Box<dyn Iterator<Item = Result<RawItem, String>> + Send>,
}

#[pymethods]
impl PyXMLIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }
    fn __next__(mut slf: PyRefMut<'_, Self>) -> PyResult<Option<PyObject>> {
        match slf.iter.next() {
            None => Ok(None),
            Some(Err(msg)) => Err(PyValueError::new_err(msg)),
            Some(Ok((count, event, payload))) => Python::with_gil(|py| {
                let event_name = match event {
                    "start" => pyo3::intern!(py, "start"),
                    "end" => pyo3::intern!(py, "end"),
                    "empty" => pyo3::intern!(py, "empty"),
                    "text" => pyo3::intern!(py, "text"),
                    _ => pyo3::intern!(py, "attr"),
                };
                let value: PyObject = match payload {
                    Payload::Str(s) => s.into_py(py),
                    Payload::Pair(name, value) => (name, value).into_py(py),
                };
                Ok(Some((count, event_name, value).into_py(py)))
            }),
        }
    }
}

struct XMLIterator {
    reader: Reader<BufReader<DecodeReaderBytes<File, Vec<u8>>>>,
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
                    let value = match str::from_utf8(e.local_name().into_inner()) {
                        Ok(v) => v.to_string(),
                        Err(_) => return Some(Err("invalid UTF-8 in tag name".into())),
                    };
                    let count = self.count;
                    self.count += 1;
                    self.open_depth += 1;
                    if self.with_attributes {
                        if let Err(msg) =
                            XMLIterator::queue_attributes(&mut self.pending, &mut self.count, &e)
                        {
                            return Some(Err(msg));
                        }
                    }
                    return Some(Ok((count, "start", Payload::Str(value))));
                }
                Event::End(e) => {
                    let value = match str::from_utf8(e.local_name().into_inner()) {
                        Ok(v) => v.to_string(),
                        Err(_) => return Some(Err("invalid UTF-8 in tag name".into())),
                    };
                    let count = self.count;
                    self.count += 1;
                    self.open_depth -= 1;
                    return Some(Ok((count, "end", Payload::Str(value))));
                }
                Event::Empty(e) => {
                    let value = match str::from_utf8(e.local_name().into_inner()) {
                        Ok(v) => v.to_string(),
                        Err(_) => return Some(Err("invalid UTF-8 in tag name".into())),
                    };
                    let count = self.count;
                    self.count += 1;
                    if self.with_attributes {
                        if let Err(msg) =
                            XMLIterator::queue_attributes(&mut self.pending, &mut self.count, &e)
                        {
                            return Some(Err(msg));
                        }
                    }
                    return Some(Ok((count, "empty", Payload::Str(value))));
                }
                Event::Text(e) => {
                    let text = match e.unescape() {
                        Ok(text) => text,
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
                    let text = match str::from_utf8(&bytes) {
                        Ok(text) => text,
                        Err(_) => return Some(Err("invalid UTF-8 in CDATA".into())),
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
    ) -> Result<(), String> {
        for attr in e.attributes() {
            let attr = attr.map_err(|err| format!("invalid attribute: {}", err))?;
            let name = str::from_utf8(attr.key.local_name().into_inner())
                .map_err(|_| "invalid UTF-8 in attribute name".to_string())?
                .to_string();
            let value = attr
                .unescape_value()
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
    let fin = File::open(path)?;
    let bufreader = BufReader::new(DecodeReaderBytes::new(fin));
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
