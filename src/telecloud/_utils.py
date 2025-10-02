import asyncio
import threading

from ..utils import write_file
from ..protector import encrypt_file, decrypt_file
from ..constants import KEY_TEST_PATH


async def encrypt_key_test(symmetric_key):
    write_file(
        KEY_TEST_PATH,
        "detect if the symmetric key is valid or not, if not then no need to start pushing/pulling files",
        mode="w",
    )

    loop = asyncio.get_running_loop()
    future = loop.create_future()

    thread = threading.Thread(
        target=encrypt_file,
        args=(symmetric_key, KEY_TEST_PATH, KEY_TEST_PATH, loop, future),
    )
    thread.start()

    await future


async def decrypt_key_test(symmetric_key):
    """
    Test the symmetric_key to check if its valid or not, if not then stop
    """
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    thread = threading.Thread(
        target=decrypt_file,
        args=(symmetric_key, KEY_TEST_PATH, KEY_TEST_PATH, loop, future),
    )
    thread.start()

    return await future
