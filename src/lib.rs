use encoding_rs_io::DecodeReaderBytes;
use pyo3::exceptions::{PyOSError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};
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
    
    // Read the first few bytes to check for BOM
    let mut bom = [0u8; 3];
    let bytes_read = fin.read(&mut bom)?;
    fin.seek(SeekFrom::Start(0))?; // Seek back to start
    
    let has_bom = if bytes_read >= 3 {
        (bom[0] == 0xEF && bom[1] == 0xBB && bom[2] == 0xBF) || // UTF-8 BOM
        (bom[0] == 0xFE && bom[1] == 0xFF) ||                   // UTF-16 BE BOM
        (bom[0] == 0xFF && bom[1] == 0xFE)                      // UTF-16 LE BOM
    } else if bytes_read >= 2 {
        (bom[0] == 0xFE && bom[1] == 0xFF) ||                   // UTF-16 BE BOM
        (bom[0] == 0xFF && bom[1] == 0xFE)                      // UTF-16 LE BOM
    } else {
        false
    };

    let reader_input: Box<dyn std::io::Read + Send> = if has_bom {
        Box::new(DecodeReaderBytes::new(fin))
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
