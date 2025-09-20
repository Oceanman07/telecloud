def read_file(file_path, mode='rb'):
    with open(file_path, mode=mode) as f:
        return f.read()

def write_file(file_path, content, mode='wb'):
    with open(file_path, mode=mode) as f:
        f.write(content)

