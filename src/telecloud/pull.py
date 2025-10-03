import json
import os
import asyncio
import threading
import time

from colorama import Style, Fore
from telethon import TelegramClient

from ._utils import encrypt_key_test, decrypt_key_test
from ..config import Config
from ..protector import decrypt_file
from ..utils import read_file, read_file_in_chunk
from ..cloudmapmanager import (
    get_cloudmap,
    get_cloud_channel_id,
    get_existed_file_names_on_cloudmap,
)
from ..constants import (
    FILE_PART_LENGTH_FOR_LARGE_FILE,
    NAMING_FILE_MAX_LENGTH,
    STORED_PREPARED_FILE_PATHS,
)

# 8 upload/retrieve files at the time
SEMAPHORE = asyncio.Semaphore(8)


async def _download_small_file(client: TelegramClient, cloud_channel, msg_id):
    msg = await client.get_messages(cloud_channel, ids=msg_id)
    file_from_cloud = os.path.join(
        STORED_PREPARED_FILE_PATHS, msg.document.attributes[0].file_name
    )
    await client.download_file(msg.document, file=file_from_cloud, part_size_kb=512)

    return file_from_cloud


def _merge_file_parts(
    file_parts, loop: asyncio.AbstractEventLoop, future: asyncio.Future
):
    any_file_part_name = os.path.basename(file_parts[0])
    any_file_part_name_without_num = any_file_part_name[
        any_file_part_name.index("_") + 1 :
    ]
    merged_file = os.path.join(
        STORED_PREPARED_FILE_PATHS,
        any_file_part_name_without_num,
    )

    with open(merged_file, "wb") as f:
        for i in range(1, len(file_parts) + 1):
            file_part = os.path.join(
                STORED_PREPARED_FILE_PATHS,
                str(i) + "_" + any_file_part_name_without_num,
            )
            for encrypted_chunk in read_file_in_chunk(file_part, is_encrypted=True):
                f.write(encrypted_chunk)
            os.remove(file_part)

    if not future.done():
        loop.call_soon_threadsafe(future.set_result, merged_file)


async def _download_big_file(client: TelegramClient, cloud_channel, msg_id):
    semaphore = asyncio.Semaphore(3)

    async def download(id):
        async with semaphore:
            msg = await client.get_messages(cloud_channel, ids=id)
            file_from_cloud = os.path.join(
                STORED_PREPARED_FILE_PATHS, msg.document.attributes[0].file_name
            )
            await client.download_file(
                msg.document, file=file_from_cloud, part_size_kb=512
            )
            return file_from_cloud

    loop = asyncio.get_running_loop()

    file_info_path = await download(msg_id)
    raw_file_info = await loop.run_in_executor(None, read_file, file_info_path, "r")
    file_parts = json.loads(raw_file_info)
    os.remove(file_info_path)

    tasks = [download(file_parts[file_part]) for file_part in file_parts]
    downloaded_file_parts = []
    for task in asyncio.as_completed(tasks):
        downloaded_file_part = await task
        downloaded_file_parts.append(downloaded_file_part)

    merged_file_value_future = loop.create_future()
    merge_file_parts_thread = threading.Thread(
        target=_merge_file_parts,
        args=(downloaded_file_parts, loop, merged_file_value_future),
    )
    merge_file_parts_thread.start()

    return await merged_file_value_future


async def _download_file(client: TelegramClient, cloud_channel, symmetric_key, file):
    async with SEMAPHORE:
        print(
            f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pulling{Style.RESET_ALL} {file['saved_path']}"
        )

        try:
            if file["file_size"] < FILE_PART_LENGTH_FOR_LARGE_FILE:
                file_from_cloud = await _download_small_file(
                    client, cloud_channel, int(file["msg_id"])
                )
            else:
                file_from_cloud = await _download_big_file(
                    client, cloud_channel, int(file["msg_id"])
                )
        except ConnectionError:
            return

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        file_decryption_thread = threading.Thread(
            target=decrypt_file,
            args=(symmetric_key, file_from_cloud, file["saved_path"], loop, future),
        )
        file_decryption_thread.start()

        await future
        os.remove(file_from_cloud)

        return file["saved_path"]


def _prepare_pulled_data(saved_directory):
    cloudmap = get_cloudmap()
    existed_file_names = get_existed_file_names_on_cloudmap()

    saved_paths = []
    for msg_id in cloudmap:
        file_name = os.path.basename(cloudmap[msg_id]["file_path"])
        file_size = cloudmap[msg_id]["file_size"]

        # If a file has multiple uploads, when downloading we need to make its name different with time
        # since it shares the same name
        if existed_file_names.count(file_name) != 1:
            differentor = "." + msg_id + "." + cloudmap[msg_id]["time"]
            base, ext = os.path.splitext(file_name)
            new_file_name = base + differentor + ext

            if len(new_file_name) > NAMING_FILE_MAX_LENGTH:
                # prevent filename reaches the limit (255 chars)
                file_name = base[: -(len(differentor) + len(ext))] + differentor + ext
            else:
                file_name = new_file_name

        saved_path = os.path.join(saved_directory, file_name)
        saved_paths.append(
            {"msg_id": msg_id, "file_size": file_size, "saved_path": saved_path}
        )

    return saved_paths


async def pull_data(client: TelegramClient, symmetric_key, config: Config):
    key_test_result = await decrypt_key_test(symmetric_key)
    if not key_test_result["success"]:
        print(
            f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}{Fore.RED} - {key_test_result['error']}{Style.RESET_ALL}"
        )
        return

    await encrypt_key_test(symmetric_key)

    cloud_channel = await client.get_entity(get_cloud_channel_id())

    if config.file:
        file = {}
        # get the lastest file
        reversed_cloudmap = dict(reversed(get_cloudmap().items()))
        for msg_id in reversed_cloudmap:
            file_name = os.path.basename(reversed_cloudmap[msg_id]["file_path"])
            if file_name == config.file:
                file["msg_id"] = msg_id
                file["file_size"] = reversed_cloudmap[msg_id]["file_size"]
                file["saved_path"] = os.path.abspath(file_name)

                result = await _download_file(
                    client, cloud_channel, symmetric_key, file
                )
                print(
                    f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pulled{Style.RESET_ALL}   {result}"
                )
                return
        print(
            f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}{Fore.RED} - File not found"
        )

    else:
        saved_dirpath = os.path.abspath(config.directory)
        os.makedirs(saved_dirpath, exist_ok=True)

        prepared_data = _prepare_pulled_data(saved_dirpath)
        tasks = [
            _download_file(client, cloud_channel, symmetric_key, file)
            for file in prepared_data
        ]

        count = 0
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
            except asyncio.exceptions.CancelledError:
                # This exception raises when pressing Ctrl+C to stop the program
                # which cancels all the coros -> return to stop immediately (no need to iterate the rest)
                return

            count += 1
            print(
                f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pulled{Style.RESET_ALL} {str(count).zfill(len(str(len(tasks))))}/{len(tasks)}   {result}"
            )
