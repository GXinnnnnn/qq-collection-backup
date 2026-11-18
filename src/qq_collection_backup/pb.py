def varint(data, pos):
    v = 0
    for shift in range(0, 70, 7):
        if pos >= len(data): raise ValueError('truncated varint')
        c = data[pos]; pos += 1; v |= (c & 127) << shift
        if not c & 128: return v, pos
    raise ValueError('long varint')

def fields(data):
    out = []; p = 0
    while p < len(data):
        tag, p = varint(data, p); num, wire = tag >> 3, tag & 7
        if not num or num > 536870911: raise ValueError('field number')
        if wire == 0: val, p = varint(data, p)
        elif wire in (1, 5):
            n = 8 if wire == 1 else 4
            if p+n > len(data): raise ValueError('fixed bounds')
            val = int.from_bytes(data[p:p+n], 'little'); p += n
        elif wire == 2:
            n, p = varint(data, p)
            if p+n > len(data): raise ValueError('length bounds')
            val = data[p:p+n]; p += n
        else: raise ValueError('unsupported wire')
        out.append((num, wire, val))
    return out

def tree(data, depth=0):
    out = []
    for num, wire, val in fields(data):
        item = {'field':num, 'wire':wire}
        if isinstance(val, bytes):
            try:
                s = val.decode('utf-8')
                if any(ord(c)<32 and c not in '\r\n\t' for c in s): raise ValueError()
                item['text'] = s
            except (UnicodeError,ValueError):
                try:
                    if depth>12 or not val: raise ValueError()
                    item['children'] = tree(val, depth+1)
                except ValueError: item['hex'] = val.hex()
        else: item['value'] = val
        out.append(item)
    return out

def leaves(nodes, prefix=''):
    for item in nodes:
        path = prefix + str(item['field'])
        if 'children' in item: yield from leaves(item['children'], path+'.')
        elif 'text' in item: yield path, item['text']
