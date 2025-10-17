import os
import asyncio
import threading

from telethon.sessions import StringSession

from . import aes, rsa
from .utils import read_file, read_file_in_chunk, write_file
from .cloudmap.functions import get_encrypted_symmetric_key
from .constants import (
    ENCRYPTED_PRIVATE_KEY_PATH,
    STRING_SESSION_PATH,
    NONCE_LENGTH,
    TAG_LENGTH,
    CHUNK_LENGTH_FOR_LARGE_FILE,
)


async def encrypt_file(key, src_path, dns_path):
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def encrypt():
        if os.path.getsize(src_path) <= CHUNK_LENGTH_FOR_LARGE_FILE:
            original_data = read_file(src_path)
            encrypted_data = aes.encrypt(key, original_data)
            write_file(dns_path, encrypted_data)
        else:
            with open(dns_path, "wb") as f:
                for chunk in read_file_in_chunk(src_path):
                    encrypted_chunk = aes.encrypt(key, chunk)
                    f.write(encrypted_chunk)

        if not future.done():
            # just await to finish the encryption process then no need to hold actual data
            loop.call_soon_threadsafe(future.set_result, None)

    encryption_thread = threading.Thread(target=encrypt, daemon=True)
    encryption_thread.start()

    await future


async def decrypt_file(key, src_path, dns_path):
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def decrypt():
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

    decryption_thread = threading.Thread(target=decrypt, daemon=True)
    decryption_thread.start()

    return await future


def load_string_session(symmetric_key):
    if not os.path.exists(STRING_SESSION_PATH):
        return StringSession()

    encrypted_session = read_file(STRING_SESSION_PATH)
    session = aes.decrypt(symmetric_key, encrypted_session)

    return StringSession(session.decode())


def load_symmetric_key(password):
    if not os.path.exists(ENCRYPTED_PRIVATE_KEY_PATH):
        return {"success": True, "symmetric_key": None}

    with open(ENCRYPTED_PRIVATE_KEY_PATH, "rb") as f:
        salt = f.read(32)
        encrypted_private_key = f.read()

    symmetric_key_for_private_key = aes.generate_key(password, salt)
    try:
        private_key = aes.decrypt(symmetric_key_for_private_key, encrypted_private_key)
    except ValueError:
        return {"success": False, "error": "Invalid password"}

    encrypted_main_symmetric_key = bytes.fromhex(get_encrypted_symmetric_key())
    main_symmetric_key = rsa.decrypt(private_key, encrypted_main_symmetric_key)
    return {"success": True, "symmetric_key": main_symmetric_key}
