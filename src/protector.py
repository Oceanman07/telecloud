import os
import asyncio

from . import aes
from .elements import EXT_IDENTIFIER
from .utils import read_file, read_file_in_chunk, write_file
from .elements import NONCE_LENGTH, TAG_LENGTH, CHUNK_LENGTH_FOR_LARGE_FILE


def encrypt_file(key, file_path, loop: asyncio.AbstractEventLoop, future: asyncio.Future):
    if os.path.getsize(file_path) <= CHUNK_LENGTH_FOR_LARGE_FILE:
        original_data = read_file(file_path)
        encrypted_data = aes.encrypt(key, original_data)
        write_file(file_path + EXT_IDENTIFIER, encrypted_data)
    else:
        with open(file_path + EXT_IDENTIFIER, 'wb') as f:
            for chunk in read_file_in_chunk(file_path):
                encrypted_chunk = aes.encrypt(key, chunk)
                f.write(encrypted_chunk)

    # just await to finish the encryption process then no need to hold data
    loop.call_soon_threadsafe(future.set_result, None)

def decrypt_file(key, file_path, loop: asyncio.AbstractEventLoop, future: asyncio.Future):
    # Plusing nonce=12bytes and tag=16bytes
    # because if the file has the exact 7MB size after encrypting it will be 12bytes + 16bytes + 7MB
    if os.path.getsize(file_path) <= NONCE_LENGTH + TAG_LENGTH + CHUNK_LENGTH_FOR_LARGE_FILE:
        encrypted_data = read_file(file_path)
        try:
            original_data = aes.decrypt(key, encrypted_data)
        except ValueError:
            loop.call_soon_threadsafe(future.set_result, {'success': False, 'error': 'Invalid password'})
            return
        # filename.txt.telecloud -> filename.txt (len('.telecloud') == 10)
        write_file(file_path[:-len(EXT_IDENTIFIER)], original_data)
    else:
        with open(file_path[:-len(EXT_IDENTIFIER)], 'wb') as f:
            for encrypted_chunk in read_file_in_chunk(file_path, is_encrypted=True):
                try:
                    original_chunk = aes.decrypt(key, encrypted_chunk)
                except ValueError:
                    loop.call_soon_threadsafe(future.set_result, {'success': False, 'error': 'Invalid password'})
                    return

                f.write(original_chunk)

    loop.call_soon_threadsafe(future.set_result, {'success': True})
