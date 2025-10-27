import os
import time
import asyncio
import threading
import json
import hashlib
import random

from colorama import Fore

from .constants import (
    NONCE_LENGTH,
    TAG_LENGTH,
    CHUNK_LENGTH_FOR_LARGE_FILE,
    PREPARED_DATA_PATH_FOR_PUSHING,
    PREPARED_DATA_PATH_FOR_PULLING,
)


def clean_prepared_data(command):
    if command == "push":
        dir_path = PREPARED_DATA_PATH_FOR_PUSHING
    else:
        dir_path = PREPARED_DATA_PATH_FOR_PULLING

    for path in os.listdir(dir_path):
        file_path = os.path.join(dir_path, path)
        os.remove(file_path)


def logging(msg):
    print(
        f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RESET} {msg}",
    )


def get_random_number():
    return str(random.randint(1000000000, 9999999999))


def read_file(file_path, mode="rb", deserialize=False):
    with open(file_path, mode=mode) as f:
        if deserialize:
            return json.load(f)
        else:
            return f.read()


def read_file_in_chunk(file_path, is_encrypted=False):
    with open(file_path, "rb") as f:
        if is_encrypted:
            while encrypted_chunk := f.read(
                NONCE_LENGTH + TAG_LENGTH + CHUNK_LENGTH_FOR_LARGE_FILE
            ):
                yield encrypted_chunk
        else:
            while chunk := f.read(CHUNK_LENGTH_FOR_LARGE_FILE):
                yield chunk


def write_file(file_path, content, mode="wb", serialize=False):
    with open(file_path, mode=mode) as f:
        if serialize:
            json.dump(content, f, ensure_ascii=False)
        else:
            f.write(content)


def get_checksum(file_path):
    checksum = hashlib.sha256()
    for chunk in read_file_in_chunk(file_path):
        checksum.update(chunk)
    return checksum.hexdigest()


async def async_get_checksum(file_path):
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def hash():
        checksum = hashlib.sha256()
        for chunk in read_file_in_chunk(file_path):
            checksum.update(chunk)

        if not future.done():
            loop.call_soon_threadsafe(future.set_result, checksum.hexdigest())

    hashing_thread = threading.Thread(target=hash, daemon=True)
    hashing_thread.start()

    return await future


def convert_bytes_to_int(bytes_num):
    b = {"KB": 1024, "MB": 1024 * 1024, "GB": 1024 * 1024 * 1024}

    num = int(bytes_num[:-2].strip())
    bytes_unit = b[bytes_num[-2:].upper()]

    return num * bytes_unit


def convert_bytes(bytes_num):
    for unit in ("bytes", "KB", "MB", "GB"):
        if bytes_num < 1024:
            return f"{round(bytes_num, 2)} {unit}"
        bytes_num /= 1024
