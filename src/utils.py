import asyncio
import hashlib
from typing import Optional

from .elements import NONCE_LENGTH, TAG_LENGTH, CHUNK_LENGTH_FOR_LARGE_FILE


def read_file(file_path, mode='rb'):
    with open(file_path, mode=mode) as f:
        return f.read()

def read_file_in_chunk(file_path, is_encrypted=False):
    with open(file_path, 'rb') as f:
        if is_encrypted:
            while encrypted_chunk := f.read(NONCE_LENGTH + TAG_LENGTH + CHUNK_LENGTH_FOR_LARGE_FILE):
                yield encrypted_chunk
        else:
            while chunk := f.read(CHUNK_LENGTH_FOR_LARGE_FILE):
                yield chunk

def write_file(file_path, content, mode='wb'):
    with open(file_path, mode=mode) as f:
        f.write(content)

def get_checksum(
        file_path,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        future: Optional[asyncio.Future] = None,
        is_holder=True):

    checksum = hashlib.sha256()
    for chunk in read_file_in_chunk(file_path):
        checksum.update(chunk)

    if not is_holder:
        return checksum.hexdigest()

    loop.call_soon_threadsafe(future.set_result, checksum.hexdigest())

