use encoding_rs_io::DecodeReaderBytes;
use pyo3::prelude::*;
use pyo3::types::{PyTuple, PyDict};
use quick_xml::{events::Event, Reader};
use std::{
    error::Error,
    fs::File,
    io::BufReader,
    str,
    collections::{HashMap},
};
const BUF_SIZE: usize = 4096; // 4kb at once

#[pymodule]
fn xml_iterator(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(iter_xml, m)?)?;
    m.add_function(wrap_pyfunction!(get_edge_counts, m)?)?;
    Ok(())
}

#[pyfunction]
fn iter_xml(path: &str) -> PyResult<PyObject> {
    Python::with_gil(|py| -> PyResult<PyObject> {
        let iterator = get_xml_iterator(path)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Failed to open XML file: {}", e)))?;
        let myiter = PyXMLIterator {
            iter: Box::new(iterator),
        };
        Ok(myiter.into_py(py))
    })
}

// this was some attempt to kind of do an xmltodict format thing ... but it is quite hard in rust.
// is there any better to do this algorithmically to avoid some of the issues with rust?
// Probably better to start with the count things routine which is simple ... just to get motivated about speed.

#[pyfunction]
fn get_edge_counts(path: &str, n_max: Option<u32>) -> PyResult<PyObject> {
    Python::with_gil(|py| -> PyResult<PyObject> {
        let iterator = get_xml_iterator(path)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(format!("Failed to open XML file: {}", e)))?;
        let mut counter: HashMap<Vec<String>, i32> = HashMap::new();
        let mut tag_stack: Vec<String> = Vec::new();
        for (count, event, value) in iterator {
            match event.as_str() {
                "start" => {
                    tag_stack.push(value.clone());
                    let count = counter.entry(tag_stack.clone()).or_insert(0);
                    *count += 1;
                }
                "text" => {
                }
                "end" => {
                    tag_stack.pop();
                }
                _ => {panic!("what")}
            }
            match n_max {
                Some(x) => {
                    if count > x { break }
                },
                None => {}
            }
        }
        // tuple = PyTuple::new(py, elements);
        // let counter = PyDict::from_sequence(py, counter.into_py(py));
        // let counter = counter.into_iter().map(|(k, v)| {(PyTuple::new(py, k), v)}).collect();
        // let counter = PyDict::from_sequence(counter.iter());
        let counter_out = PyDict::new(py);
        for (k, v) in counter.into_iter() {
            let k = PyTuple::new(py, k);
            let _ = counter_out.set_item(k, v);
        }
        Ok(counter_out.into_py(py))

    })
}


// struct NestedThing {
//     x: LinkedList<HashMap<String, NestedThing>>,
// }

// #[pyfunction]
// fn read_xml(path: &str) -> PyResult<PyObject> {
//     // see https://stackoverflow.com/questions/59640315/how-do-i-define-a-nested-hashmap-with-an-unknown-nesting-level 
//     Python::with_gil(|py| -> PyResult<PyObject> {
//         let iterator = get_xml_iterator(path).unwrap();
//         // let mut d = HashMap::new();
//         let out = NestedThing{x: LinkedList::new()};
//         // let mut back = NestedThing{x: LinkedList::new()};
//         let back: LinkedList<NestedThing> = LinkedList::new();  // this is just a stack
//         let cur = out;
//         for (count, event, value) in iterator {
//             match event.as_str() {
//                 "start" => {
//                     let entry = HashMap::from([(value, NestedThing{x: LinkedList::new()})]);
//                     cur.x.push_back(entry);
//                     // back.push_back(cur);
//                     // let cur = back.back().unwrap().back().unwrap().entry(value);
//                 }
//                 "text" => {
//                     // cur.push_back(
//                     //     HashMap::from(
//                     //         [("text".to_string(), LinkedList::from([value]))]
//                     //     )
//                     // );
//                 }
//                 "end" => {
//                     // let cur = back.pop_back().unwrap();
//                 }
//                 _ => {panic!("what")}
//             }
//         }
//         Ok("asdf".into_py(py))
//     })
// }

type ItemType = (u32, String, String);

#[pyclass]
struct PyXMLIterator {
    iter: Box<dyn Iterator<Item = ItemType> + Send>,
}

#[pymethods]
impl PyXMLIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }
    fn __next__(mut slf: PyRefMut<'_, Self>) -> Option<PyObject> {
        let rust_tuple = slf.iter.next();
        if rust_tuple.is_none() {
            return None
        } else {
            Python::with_gil(|py| -> Option<PyObject> {
                Some(rust_tuple.unwrap().into_py(py))
            })
        }
    }
}

struct XMLIterator {
    reader: Reader<BufReader<DecodeReaderBytes<File, Vec<u8>>>>,
    count: u32,
}

impl Iterator for XMLIterator {
    type Item = (u32, String, String);
    fn next(&mut self) -> Option<Self::Item> {
        /* NOTE: this ingored attribute values see below if you need that */
        let mut buf: Vec<u8> = Vec::with_capacity(BUF_SIZE);
        self.count += 1;
        loop {
            match self.reader.read_event_into(&mut buf).ok()? {
                Event::Start(e) => {
                    let value = str::from_utf8(e.local_name().into_inner()).ok()?.to_string();
                    break Some((self.count - 1, "start".to_string(), value))
                }
                Event::End(e) => {
                    let value = str::from_utf8(e.local_name().into_inner()).ok()?.to_string();
                    break Some((self.count - 1, "end".to_string(), value))
                }
                Event::Empty(e) => {
                    let value = str::from_utf8(e.local_name().into_inner()).ok()?.to_string();
                    break Some((self.count - 1, "empty".to_string(), value))
                }
                Event::Text(e) => {
                    let value = match e.unescape() {
                        Ok(text) => text.trim().to_owned(),
                        Err(_) => continue, // Skip invalid text content
                    };
                    if value == "" { continue }
                    break Some((self.count - 1, "text".to_string(), value))
                }
                Event::Eof => {
                    break None
                }
                _ => {continue}
            }
        }
    }
}


fn get_xml_iterator(path: &str) -> Result<XMLIterator, Box<dyn Error>> {
    println!("xml_iterator::reading {:?}", path);
    let fin = File::open(path)?;
    let bufreader = BufReader::new(DecodeReaderBytes::new(fin));
    let reader = Reader::from_reader(bufreader);
    let reader_iter = XMLIterator {reader: reader, count: 0};
    Ok(reader_iter)
}
