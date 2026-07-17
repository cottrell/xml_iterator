#!/usr/bin/env python
"""Stream FIRDS-like records under wrappers that stay open until EOF.

Protection against the infinite depth attack: process each FinInstrm on its end
event while RefData/Payload/root remain open; discard finished work; early-stop.
Do not use full-file xml_to_dict for multi-GB dumps of this shape.
"""

import os
import tempfile

from xml_iterator.xml_iterator import iter_xml


def write_firds_like(path: str, n: int = 20) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0"?><root><Payload><RefData>')
        for i in range(n):
            f.write(f"<FinInstrm><Id>{i}</Id></FinInstrm>")
        f.write("</RefData></Payload></root>")


def main() -> None:
    fd, path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        write_firds_like(path, n=20)
        k = 5
        records = 0
        for count, event, value in iter_xml(path):
            if event == "end" and value == "FinInstrm":
                records += 1
                print(f"record {records} complete at event {count} (outers still open)")
                if records >= k:
                    print(f"early stop after {k} records (file has more)")
                    break
    finally:
        os.unlink(path)


if __name__ == "__main__":
    main()
