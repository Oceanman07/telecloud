import os
import asyncio
import threading

from . import aes
from .utils import read_file, read_file_in_chunk, write_file
from .constants import (
    STRING_SESSION_PATH,
    NONCE_LENGTH,
    TAG_LENGTH,
    CHUNK_LENGTH_FOR_LARGE_FILE,
)


def encrypt_file(
    key, src_path, dns_path, loop: asyncio.AbstractEventLoop, future: asyncio.Future
):
    if os.path.getsize(src_path) <= CHUNK_LENGTH_FOR_LARGE_FILE:
        original_data = read_file(src_path)
        encrypted_data = aes.encrypt(key, original_data)
        write_file(dns_path, encrypted_data)
    else:
        with open(dns_path, "wb") as f:
            for chunk in read_file_in_chunk(src_path):
                encrypted_chunk = aes.encrypt(key, chunk)
                f.write(encrypted_chunk)

    if loop and future:
        if not future.done():
            # just await to finish the encryption process then no need to hold data
            loop.call_soon_threadsafe(future.set_result, None)


def decrypt_file(
    key, src_path, dns_path, loop: asyncio.AbstractEventLoop, future: asyncio.Future
):
    # Plusing nonce=12bytes and tag=16bytes
    # because if the file has the exact 7MB size after encrypting it will be 12bytes + 16bytes + 7MB
    if (
        os.path.getsize(src_path)
        <= NONCE_LENGTH + TAG_LENGTH + CHUNK_LENGTH_FOR_LARGE_FILE
    ):
        encrypted_data = read_file(src_path)
        try:
            original_data = aes.decrypt(key, encrypted_data)
        except ValueError:
            loop.call_soon_threadsafe(
                future.set_result, {"success": False, "error": "Invalid password"}
            )
            return

        write_file(dns_path, original_data)

    else:
        with open(dns_path, "wb") as f:
            for encrypted_chunk in read_file_in_chunk(src_path, is_encrypted=True):
                try:
                    original_chunk = aes.decrypt(key, encrypted_chunk)
                except ValueError:
                    loop.call_soon_threadsafe(
                        future.set_result,
                        {"success": False, "error": "Invalid password"},
                    )
                    return

                f.write(original_chunk)

    if not future.done():
        loop.call_soon_threadsafe(future.set_result, {"success": True})


async def encrypt_string_session(symmetric_key):
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    thread = threading.Thread(
        target=encrypt_file,
        args=(symmetric_key, STRING_SESSION_PATH, STRING_SESSION_PATH, loop, future),
    )
    thread.start()

    await future


async def decrypt_string_session(symmetric_key):
    loop = asyncio.get_running_loop()

    decryption_value_future = loop.create_future()
    decrypt_string_session_thread = threading.Thread(
        target=decrypt_file,
        args=(
            symmetric_key,
            STRING_SESSION_PATH,
            STRING_SESSION_PATH,
            loop,
            decryption_value_future,
        ),
    )
    decrypt_string_session_thread.start()

    return await decryption_value_future
