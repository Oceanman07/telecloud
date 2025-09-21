import hashlib


def read_file(file_path, mode='rb'):
    with open(file_path, mode=mode) as f:
        return f.read()

def read_file_in_chunk(file_path):
    with open(file_path, 'rb') as f:
        while chunk := f.read(7 * 1024 * 1024):
            yield chunk

def write_file(file_path, content, mode='wb'):
    with open(file_path, mode=mode) as f:
        f.write(content)

def get_checksum(file_path, checksum_holder={}, is_holder=True):
    checksum = hashlib.sha256()
    for chunk in read_file_in_chunk(file_path):
        checksum.update(chunk)

    if not is_holder:
        return checksum.hexdigest()

    checksum_holder['checksum'] = checksum.hexdigest()

