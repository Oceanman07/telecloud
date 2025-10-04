import json
import os
import asyncio
import threading
import time

from colorama import Style, Fore
from telethon import TelegramClient

from ._utils import encrypt_key_test, decrypt_key_test
from ..config import Config
from ..protector import encrypt_file
from ..constants import FILE_PART_LENGTH_FOR_LARGE_FILE, STORED_PREPARED_FILE_PATHS
from ..utils import (
    get_checksum,
    get_random_number,
    write_file,
    read_file_in_chunk,
)
from ..cloudmapmanager import (
    get_cloud_channel_id,
    get_cloudmap,
    update_cloudmap,
    get_existed_checksums,
    get_existed_file_paths_on_cloudmap,
)

# 8 upload/retrieve files at the time
SEMAPHORE = asyncio.Semaphore(8)


async def _upload_small_file(client: TelegramClient, cloud_channel, file_path):
    file = await client.upload_file(file_path, file_name=file_path, part_size_kb=512)
    msg = await client.send_file(cloud_channel, file)
    os.remove(file_path)

    return msg.id


def _split_big_file(file_path, loop: asyncio.AbstractEventLoop, future: asyncio.Future):
    file_parts = []
    max_split_times = 7
    split_count = 0
    part_num = 1
    written_size = 0

    size_file = os.path.getsize(file_path)
    for encrypted_chunk in read_file_in_chunk(file_path, is_encrypted=True):
        file_part = os.path.join(
            STORED_PREPARED_FILE_PATHS,
            str(part_num) + "_" + os.path.basename(file_path),
        )
        with open(file_part, "ab") as f:
            f.write(encrypted_chunk)
            written_size += len(encrypted_chunk)

        split_count += 1
        if split_count == max_split_times:
            part_num += 1
            file_parts.append(file_part)
            split_count = 0

        elif written_size >= size_file:
            file_parts.append(file_part)

    if not future.done():
        loop.call_soon_threadsafe(future.set_result, file_parts)


async def _upload_big_file(client: TelegramClient, cloud_channel, file_path):
    semaphore = asyncio.Semaphore(3)

    async def upload(file_part):
        async with semaphore:
            try:
                file = await client.upload_file(
                    file_part, file_name=file_part, part_size_kb=512
                )
                msg = await client.send_file(cloud_channel, file)
                os.remove(file_part)

                return {file_part: msg.id}

            except ConnectionError:
                return

    loop = asyncio.get_running_loop()

    # Split the big file into multiple smaller files
    # -> prevent reaching over 2GB max
    # -> faster when sending concurrency part files
    file_parts_value_future = loop.create_future()
    split_big_file_thread = threading.Thread(
        target=_split_big_file, args=(file_path, loop, file_parts_value_future)
    )
    split_big_file_thread.start()

    file_parts = await file_parts_value_future
    os.remove(file_path)

    upload_info = {}
    tasks = [upload(file) for file in file_parts]
    for task in asyncio.as_completed(tasks):
        msg_id = await task
        upload_info.update(msg_id)

    # upload_info just contains msg_id of file_parts then no need to encrypt
    upload_info_path = os.path.join(
        STORED_PREPARED_FILE_PATHS, "0_" + os.path.basename(file_path)
    )
    await loop.run_in_executor(
        None, write_file, upload_info_path, json.dumps(upload_info), "w"
    )
    msg = await upload(upload_info_path)

    return msg[upload_info_path]


async def _upload_file(client: TelegramClient, cloud_channel, symmetric_key, file_path):
    async with SEMAPHORE:
        print(
            f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pushing{Style.RESET_ALL} {file_path}"
        )

        loop = asyncio.get_running_loop()

        # hash file content -> get checksum
        checksum_value_future = loop.create_future()
        hash_checksum_thread = threading.Thread(
            target=get_checksum, args=(file_path, loop, checksum_value_future)
        )
        hash_checksum_thread.start()

        # checksum is now the name of encrypted file -> prevent long file name from reaching over 255 chars
        # adding random number to prevent checksum name conflict > two different files could have the same data
        checksum = await checksum_value_future
        encrypted_file_path = os.path.join(
            STORED_PREPARED_FILE_PATHS, get_random_number() + "_" + checksum
        )

        # encrypt file before uploading to cloud
        encryption_process_future = loop.create_future()
        file_encryption_thread = threading.Thread(
            target=encrypt_file,
            args=(
                symmetric_key,
                file_path,
                encrypted_file_path,
                loop,
                encryption_process_future,
            ),
            daemon=True,
        )
        file_encryption_thread.start()

        await encryption_process_future

        try:
            file_size = os.path.getsize(file_path)
            if file_size < FILE_PART_LENGTH_FOR_LARGE_FILE:
                msg_id = await _upload_small_file(
                    client, cloud_channel, encrypted_file_path
                )
            else:
                msg_id = await _upload_big_file(
                    client, cloud_channel, encrypted_file_path
                )
        except ConnectionError:
            return

        return {
            "msg_id": msg_id,
            "attrib": {
                "checksum": checksum,
                "file_path": file_path,
                "file_size": file_size,
                "time": time.strftime("%d-%m-%y.%H-%M-%S"),
            },
        }


def _prepare_pushed_data(
    root_directory,
    excluded_dirs,
    excluded_files,
    excluded_file_suffixes,
    max_size,
    is_recursive,
):
    existed_file_paths = get_existed_file_paths_on_cloudmap()
    checksums = get_existed_checksums()

    file_paths = []
    for dir_path, _, file_names in os.walk(root_directory):
        if os.path.basename(dir_path) in excluded_dirs:
            continue

        for file_name in file_names:
            file_path = os.path.join(dir_path, file_name)

            if file_name in excluded_files:
                continue
            if any(file_name.endswith(suffix) for suffix in excluded_file_suffixes):
                continue
            if os.path.getsize(file_path) > max_size:
                continue

            if file_path not in existed_file_paths:
                file_paths.append(file_path)
                continue

            if get_checksum(file_path, None, None, is_holder=False) not in checksums:
                file_paths.append(file_path)
                continue

            print(
                f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Remained{Style.RESET_ALL}   {file_path}"
            )

        if not is_recursive:
            break

    return file_paths


async def push_data(client: TelegramClient, symmetric_key, config: Config):
    key_test_result = await decrypt_key_test(symmetric_key)
    if not key_test_result["success"]:
        print(
            f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}{Fore.RED} - Password does not match{Style.RESET_ALL}"
        )
        return

    await encrypt_key_test(symmetric_key)

    loop = asyncio.get_running_loop()
    new_cloudmap = get_cloudmap()
    cloud_channel = await client.get_entity(get_cloud_channel_id())

    if config.file:
        file_path = os.path.abspath(config.file)
        if not os.path.exists(file_path):
            print(
                f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}{Fore.RED} - File not found"
            )
            return
        try:
            result = await _upload_file(client, cloud_channel, symmetric_key, file_path)
            new_cloudmap[result["msg_id"]] = result["attrib"]
            await loop.run_in_executor(None, update_cloudmap, new_cloudmap)
            print(
                f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pushed{Style.RESET_ALL}   {result['attrib']['file_path']}"
            )
        except asyncio.exceptions.CancelledError:
            return

    else:
        dir_path = os.path.abspath(config.directory)
        if not os.path.exists(dir_path):
            print(
                f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}{Fore.RED} - Directory not found"
            )
            return

        prepared_data = _prepare_pushed_data(
            root_directory=dir_path,
            excluded_dirs=config.excluded_dirs,
            excluded_files=config.excluded_files,
            excluded_file_suffixes=config.excluded_file_suffixes,
            max_size=config.max_size,
            is_recursive=config.is_recursive,
        )
        tasks = [
            _upload_file(client, cloud_channel, symmetric_key, file_path)
            for file_path in prepared_data
        ]

        count = 0
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
            except asyncio.exceptions.CancelledError:
                # This exception raises when pressing Ctrl+C to stop the program
                # which cancels all the coros -> return to stop immediately (no need to iterate the rest)
                return

            new_cloudmap[result["msg_id"]] = result["attrib"]
            await loop.run_in_executor(None, update_cloudmap, new_cloudmap)

            count += 1
            print(
                f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pushed{Style.RESET_ALL} {str(count).zfill(len(str(len(tasks))))}/{len(tasks)}   {result['attrib']['file_path']}"
            )
