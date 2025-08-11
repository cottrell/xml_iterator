from collections import defaultdict
from xml_iterator.xml_iterator import iter_xml

def get_edge_counts(filename, n_max=None):
    """
    Consider nested xml attributes. An edge (a.b, c) simply means an entry

        <a ...><b ...><c ...>....

    and note that we only count start events.
    """
    iter_in = iter_xml(filename)
    counter = defaultdict(int)
    tag_stack = list()
    for (count, event, value) in iter_in:
        if event == 'start':
            tag_stack.append(value)
            key = tuple(tag_stack)
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
    for (count, event, value) in iter_in:
        if event == 'start':
            cur.append({value: []})
            back.append(cur)
            cur = cur[-1][value]
            tag_stack.append(value)
        elif event == 'text':
            cur.append(dict(text=value))
        elif event == 'end':
            cur = back.pop()
            key = tuple(tag_stack)
            counter[key] += 1
            assert tag_stack[-1] == value, f'{value} != {tag_stack[-1]}'
            tag_stack.pop()
        else:
            raise Exception(f'event = {event}!?')
        if n_max is not None:
            if count > n_max:
                break
    counter = dict(counter)
    # do not do this it breaks the plotting format which needs tuples
    # counter = {'.'.join(k): v for k, v in counter.items()}
    return out, counter

def reduce_length_one_lists_recursively(x_in):
    if isinstance(x_in, list):
        keys = [tuple(x.keys()) for x in x_in]
        assert max(map(len, keys)) == 1
        if len(set(keys)) == len(keys):
            keys = [k[0] for k in keys]
            values = [tuple(x.values())[0] for x in x_in]
            return {k: reduce_length_one_lists_recursively(v) for k, v in zip(keys, values) if v}
        else:
            return [{k: reduce_length_one_lists_recursively(v) for k, v in x.items()} for x in x_in if x]
    else:
        return x_in


def xml_to_dict(filename, max_depth=None, max_events=None):
    """
    Convert XML to dictionary structure similar to xmltodict.
    
    Args:
        filename: Path to XML file
        max_depth: Optional maximum nesting depth (for protection)
        max_events: Optional maximum number of events to process
    
    Returns:
        Dictionary representation of XML
    """
    stack = []
    root = None
    event_count = 0
    
    for count, event, value in iter_xml(filename):
        event_count += 1
        
        # Optional limits for protection
        if max_events and event_count > max_events:
            break
        if max_depth and len(stack) > max_depth:
            continue
            
        if event == 'start':
            # Create new element
            element = {'_tag': value, '_children': [], '_text': None}
            
            if root is None:
                root = element
            else:
                # Add to parent's children
                stack[-1]['_children'].append(element)
            
            stack.append(element)
            
        elif event == 'empty':
            # Self-closing tag - create element and don't push to stack
            element = {'_tag': value, '_children': [], '_text': None}
            
            if root is None:
                root = element
            else:
                # Add to parent's children
                stack[-1]['_children'].append(element)
            
        elif event == 'text':
            if stack and value.strip():
                # Add text to current element
                if stack[-1]['_text'] is None:
                    stack[-1]['_text'] = value
                else:
                    stack[-1]['_text'] += value
                    
        elif event == 'end':
            if stack:
                stack.pop()
    
    return _normalize_dict(root) if root else {}


def _normalize_dict(element):
    """
    Convert internal representation to clean dictionary format.
    """
    if not element:
        return None
        
    result = {}
    tag = element['_tag']
    text = element['_text']
    children = element['_children']
    
    # Group children by tag name
    child_groups = defaultdict(list)
    for child in children:
        child_tag = child['_tag']
        normalized_child = _normalize_dict(child)
        # Extract the content from the wrapped dict
        if isinstance(normalized_child, dict) and child_tag in normalized_child:
            child_groups[child_tag].append(normalized_child[child_tag])
        else:
            child_groups[child_tag].append(normalized_child)
    
    # Convert child groups to final format
    content = {}
    for child_tag, child_list in child_groups.items():
        if len(child_list) == 1:
            content[child_tag] = child_list[0]
        else:
            content[child_tag] = child_list
    
    # Handle text content
    if text and text.strip():
        if content:
            # Mixed content - put text in special key
            content['#text'] = text.strip()
        else:
            # Text-only element - return just the text
            content = text.strip()
    
    # Return None for truly empty elements
    if not content and not text:
        content = None
    
    # Always wrap in tag name to match xmltodict behavior
    return {tag: content}


def xml_to_dict_simple(filename, max_events=None):
    """
    Simple XML to dict converter - flattens structure more aggressively.
    Similar to xmltodict behavior.
    """
    stack = [{}]
    path_stack = []
    event_count = 0
    
    for count, event, value in iter_xml(filename):
        event_count += 1
        if max_events and event_count > max_events:
            break
            
        if event == 'start':
            path_stack.append(value)
            # Create nested structure
            current = stack[-1]
            for tag in path_stack:
                if tag not in current:
                    current[tag] = {}
                elif not isinstance(current[tag], dict):
                    # Convert to list if multiple elements with same tag
                    current[tag] = [current[tag], {}]
                    current = current[tag][-1]
                    break
                current = current[tag]
            stack.append(current)
            
        elif event == 'text':
            if stack and path_stack and value.strip():
                current = stack[-1]
                text_value = value.strip()
                
                if not current:  # Empty dict - make it the text value
                    # Need to replace in parent
                    if len(stack) > 1:
                        parent = stack[-2]
                        tag = path_stack[-1]
                        parent[tag] = text_value
                else:
                    # Mixed content
                    if '#text' not in current:
                        current['#text'] = text_value
                    else:
                        current['#text'] += ' ' + text_value
                        
        elif event == 'end':
            if path_stack:
                path_stack.pop()
            if len(stack) > 1:
                stack.pop()
    
    return stack[0]

