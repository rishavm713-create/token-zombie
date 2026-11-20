def read_numbers(path):
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                out.append(float(line.split(',')[0]))
    return out
