#!/usr/bin/env python
from xml_iterator.xml_iterator import get_edge_counts, iter_xml

# wget https://www.w3schools.com/xml/simple.xml
filename = 'simple.xml'

print('\nget_edge_counts:')
print(get_edge_counts(filename))

print('\niter_xml:')
for x in iter_xml(filename):
    print(x)
