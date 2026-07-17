from collections import defaultdict

from xml_iterator.xml_iterator import iter_xml
from xml_iterator.xml_iterator import xml_to_dict as _xml_to_dict_rust


def get_edge_counts(filename, n_max=None):
    """
    Consider nested xml attributes. An edge (a.b, c) simply means an entry

        <a ...><b ...><c ...>....

    and note that we only count start and self-closing events.
    """
    iter_in = iter_xml(filename)
    counter = defaultdict(int)
    tag_stack = list()
    for count, event, value in iter_in:
        if event == 'start':
            tag_stack.append(value)
            key = tuple(tag_stack)
            counter[key] += 1
        elif event == 'empty':
            key = tuple(tag_stack + [value])
            counter[key] += 1
        elif event == 'end':
            assert tag_stack[-1] == value, f'{value} != {tag_stack[-1]}'
            tag_stack.pop()
        if n_max is not None:
            if count > n_max:
                break
    return dict(counter)


def read_records(filename, n_max=None):
    # NOTE: this is probably what to use
    iter_in = iter_xml(filename)
    counter = defaultdict(int)
    tag_stack = list()
    out = []
    back = []
    cur = out
    # on start: append new entry, update cur and back
    # on end: update cur and back
    # on text: update cur with {'text': value} or just value?
    for count, event, value in iter_in:
        if event == 'start':
            cur.append({value: []})
            back.append(cur)
            cur = cur[-1][value]
            tag_stack.append(value)
        elif event == 'empty':
            cur.append({value: []})
            key = tuple(tag_stack + [value])
            counter[key] += 1
        elif event == 'text':
            cur.append(dict(text=value))
        elif event == 'end':
            cur = back.pop()
            key = tuple(tag_stack)
            counter[key] += 1
            assert tag_stack[-1] == value, f'{value} != {tag_stack[-1]}'
            tag_stack.pop()
        if n_max is not None:
            if count > n_max:
                break
    counter = dict(counter)
    # do not do this it breaks the plotting format which needs tuples
    # counter = {'.'.join(k): v for k, v in counter.items()}
    return out, counter


def xml_to_dict(filename, max_depth=None, max_events=None):
    """Convert XML to dictionary structure matching xmltodict.parse output (Rust implementation)."""
    return _xml_to_dict_rust(filename, max_depth, max_events)


def xml_to_dict_py(filename, max_depth=None, max_events=None):
    """Reference Python implementation of xml_to_dict; kept for parity tests."""
    stack = []
    root = None
    event_count = 0
    last_element = None
    skipping = 0

    for count, event, value in iter_xml(filename, attributes=True):
        event_count += 1

        if max_events is not None and event_count > max_events:
            break

        if event == 'start':
            if skipping:
                skipping += 1
                continue
            if max_depth is not None and len(stack) >= max_depth:
                skipping = 1
                continue
            element = {'_tag': value, '_attrs': {}, '_children': [], '_text': None}
            if root is None:
                root = element
            else:
                stack[-1]['_children'].append(element)
            stack.append(element)
            last_element = element

        elif event == 'empty':
            if skipping or (max_depth is not None and len(stack) >= max_depth):
                continue
            element = {'_tag': value, '_attrs': {}, '_children': [], '_text': None}
            if root is None:
                root = element
            else:
                stack[-1]['_children'].append(element)
            last_element = element

        elif event == 'attr':
            if skipping:
                continue
            name, attr_value = value
            if last_element is not None:
                last_element['_attrs'][name] = attr_value

        elif event == 'text':
            if skipping:
                continue
            if stack and value.strip():
                if stack[-1]['_text'] is None:
                    stack[-1]['_text'] = value
                else:
                    stack[-1]['_text'] += value

        elif event == 'end':
            if skipping:
                skipping -= 1
                continue
            if stack:
                stack.pop()

    return _normalize_dict(root) if root else {}


def _normalize_dict(root):
    """
    Convert internal representation to clean dictionary format, matching
    xmltodict.parse semantics: iterative post-order traversal (no recursion
    limit on deep documents).
    """
    contents = {}
    stack = [(root, False)]
    while stack:
        element, visited = stack.pop()
        elem_id = id(element)
        if not visited:
            stack.append((element, True))
            for child in reversed(element['_children']):
                stack.append((child, False))
            continue

        content = {}
        for name, attr_value in element['_attrs'].items():
            content[f'@{name}'] = attr_value

        child_groups = {}
        child_order = []
        for child in element['_children']:
            child_tag = child['_tag']
            child_content = contents[id(child)]
            if child_tag not in child_groups:
                child_groups[child_tag] = []
                child_order.append(child_tag)
            child_groups[child_tag].append(child_content)

        for child_tag in child_order:
            child_list = child_groups[child_tag]
            content[child_tag] = child_list[0] if len(child_list) == 1 else child_list

        text = element['_text']
        text = text.strip() if text else None
        if text:
            if content:
                content['#text'] = text
            else:
                content = text

        if not content:
            content = None

        contents[elem_id] = content

    return {root['_tag']: contents[id(root)]}
