import os
import asyncio
import threading
import time

from colorama import Fore
from telethon import TelegramClient

from ..config import Config
from ..protector import encrypt_file
from ..constants import CHUNK_LENGTH_FOR_LARGE_FILE, STORED_PREPARED_FILE_PATHS
from ..utils import (
    get_checksum,
    async_get_checksum,
    get_random_number,
    write_file,
    read_file_in_chunk,
)
from ..cloudmap.functions import (
    get_cloudmap,
    update_cloudmap,
    get_cloud_channel_id,
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


async def _split_big_file(file_path):
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def split():
        file_parts = []
        max_split_times = 1
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

    splitting_thread = threading.Thread(target=split, daemon=True)
    splitting_thread.start()

    return await future


async def _upload_big_file(
    client: TelegramClient, cloud_channel, file_path, is_single_file=False
):
    if is_single_file:
        semaphore = asyncio.Semaphore(8)
    else:
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

            except FileNotFoundError:
                # This exception raises when trying to stop the program during sending file parts (from big file)
                # in the main thread the program will call clean_prepared_data which cleans all the encrypted file parts
                # and the pushing process (_upload_big_file) may touch that one encrypted file part
                # and that part is already deleted (clean by clean_prepared_data) -> FileNotFoundError
                return

    # Split the big file into multiple smaller files
    # -> prevent reaching over 2GB max
    # -> faster when sending concurrency part files
    file_parts = await _split_big_file(file_path)
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
    await asyncio.get_running_loop().run_in_executor(
        None, write_file, upload_info_path, upload_info, "w", True
    )
    msg = await upload(upload_info_path)

    return msg[upload_info_path]


async def _upload_file(
    client: TelegramClient,
    cloud_channel,
    symmetric_key,
    file_path,
    is_single_file=False,
):
    async with SEMAPHORE:
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.YELLOW} Pushing{Fore.RESET} {file_path}"
        )
        # checksum is now the name of encrypted file -> prevent long file name from reaching over 255 chars
        # adding random number to prevent checksum name conflict > two different files could have the same data
        checksum = await async_get_checksum(file_path)
        encrypted_file_path = os.path.join(
            STORED_PREPARED_FILE_PATHS, get_random_number() + "_" + checksum
        )
        # encrypt file before uploading to cloud
        await encrypt_file(symmetric_key, file_path, encrypted_file_path)

        try:
            file_size = os.path.getsize(file_path)
            if file_size < CHUNK_LENGTH_FOR_LARGE_FILE:
                msg_id = await _upload_small_file(
                    client, cloud_channel, encrypted_file_path
                )
            else:
                msg_id = await _upload_big_file(
                    client,
                    cloud_channel,
                    encrypted_file_path,
                    is_single_file=is_single_file,
                )
        except ConnectionError:
            # This exception raises when pressing Ctrl+C to stop the program
            # which cancels all the tasks -> ConnectionError will be raised in client.upload_file
            # sleep for 0.1 seconds just to hit an await
            # basically if we just return without letting the coro hit an await
            # -> the cancellation will stay pending (it does not know its already cancelled until it hit an await)
            # though in this case, we do not even need to await sleep()
            # since at the end it just returns a dict (not doing work like download_file) -> but still a good practice
            # also the return statement is not necessary at all
            # just to make it less confused whenever come back to read code
            # -> its like Ah! return to stop the function (instead of why sleep for 0.1 after catching error then return the info???)
            await asyncio.sleep(0.1)
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
    filter_name_func,
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
            if not os.path.getsize(file_path) <= max_size:
                continue
            if not filter_name_func(file_name):
                continue

            if file_path not in existed_file_paths:
                file_paths.append(file_path)
                continue

            if get_checksum(file_path) not in checksums:
                file_paths.append(file_path)
                continue

            print(
                f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Remained{Fore.RESET}   {file_path}"
            )

        if not is_recursive:
            break

    return file_paths


async def push_data(client: TelegramClient, symmetric_key, config: Config):
    new_cloudmap = get_cloudmap()
    cloud_channel = await client.get_entity(get_cloud_channel_id())

    if config.target_path["is_file"]:
        try:
            result = await _upload_file(
                client,
                cloud_channel,
                symmetric_key,
                config.target_path["value"],
                is_single_file=True,
            )
            new_cloudmap[result["msg_id"]] = result["attrib"]
            await update_cloudmap(new_cloudmap)
            print(
                f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pushed{Fore.RESET}   {result['attrib']['file_path']}"
            )
        except asyncio.exceptions.CancelledError:
            return

    else:
        prepared_data = _prepare_pushed_data(
            root_directory=config.target_path["value"],
            excluded_dirs=config.excluded_dirs,
            excluded_files=config.excluded_files,
            excluded_file_suffixes=config.excluded_file_suffixes,
            max_size=config.max_size,
            is_recursive=config.is_recursive,
            filter_name_func=config.filter_name_func,
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
            await update_cloudmap(new_cloudmap)

            count += 1
            print(
                f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pushed{Fore.RESET} {str(count).zfill(len(str(len(tasks))))}/{len(tasks)}   {result['attrib']['file_path']}"
            )
