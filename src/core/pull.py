import os
import asyncio
import threading
import time

from colorama import Fore
from telethon import TelegramClient

from ..config import Config
from ..protector import decrypt_file
from ..utils import read_file, read_file_in_chunk
from ..cloudmapmanager import (
    get_cloudmap,
    get_cloud_channel_id,
    get_existed_file_names_on_cloudmap,
)
from ..constants import (
    NAMING_FILE_MAX_LENGTH,
    STORED_PREPARED_FILE_PATHS,
    CHUNK_LENGTH_FOR_LARGE_FILE,
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


async def _merge_file_parts(file_parts):
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def merge():
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

    merging_thread = threading.Thread(target=merge, daemon=True)
    merging_thread.start()

    return await future


async def _download_big_file(
    client: TelegramClient, cloud_channel, msg_id, is_single_file=False
):
    if is_single_file:
        semaphore = asyncio.Semaphore(8)
    else:
        semaphore = asyncio.Semaphore(3)

    async def download(id):
        async with semaphore:
            try:
                msg = await client.get_messages(cloud_channel, ids=id)
                file_from_cloud = os.path.join(
                    STORED_PREPARED_FILE_PATHS, msg.document.attributes[0].file_name
                )
                await client.download_file(
                    msg.document, file=file_from_cloud, part_size_kb=512
                )
                return file_from_cloud

            except ConnectionError:
                return

    file_info_path = await download(msg_id)
    if file_info_path is None:
        # file_info_path is None when pressing Ctrl+C to stop the program
        # which cancels all the tasks -> client.download_file coro will raise ConnectionError
        # after that the worker download will return to stop -> None
        return
    file_parts = await asyncio.get_running_loop().run_in_executor(
        None, read_file, file_info_path, "r", True
    )
    os.remove(file_info_path)

    tasks = [download(file_parts[file_part]) for file_part in file_parts]
    downloaded_file_parts = []
    for task in asyncio.as_completed(tasks):
        downloaded_file_part = await task
        downloaded_file_parts.append(downloaded_file_part)

    return await _merge_file_parts(downloaded_file_parts)


async def _download_file(
    client: TelegramClient, cloud_channel, symmetric_key, file, is_single_file=False
):
    async with SEMAPHORE:
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.YELLOW} Pulling{Fore.RESET} {file['saved_path']}"
        )
        try:
            if file["file_size"] < CHUNK_LENGTH_FOR_LARGE_FILE:
                file_from_cloud = await _download_small_file(
                    client, cloud_channel, int(file["msg_id"])
                )
            else:
                file_from_cloud = await _download_big_file(
                    client,
                    cloud_channel,
                    int(file["msg_id"]),
                    is_single_file=is_single_file,
                )
        except ConnectionError:
            # This exception raises when pressing Ctrl+C to stop the program
            # which cancels all the tasks -> ConnectionError will be raised in client.download_file
            # sleep for 0.1 seconds just to hit an await cause if this coro does not hit in here
            # -> it will skip the return statement and move on decrypt_file (which will continue to process)
            # basically if we just return without letting the coro hit an await
            # -> the cancellation will stay pending (it does not know its already cancelled until it hit an await)
            # also the return statement is not necessary at all
            # just to make it less confused whenever come back to read code
            # -> its like Ah! return to stop the function (instead of why sleep for 0.1 after catching error then decrypt???)
            await asyncio.sleep(0.1)
            return

        await decrypt_file(symmetric_key, file_from_cloud, file["saved_path"])
        os.remove(file_from_cloud)

        return file["saved_path"]


def _prepare_pulled_data(
    saved_directory,
    excluded_files,
    excluded_file_suffixes,
    max_size,
    filter_name_func,
):
    cloudmap = get_cloudmap()
    existed_file_names = get_existed_file_names_on_cloudmap()
    pulled_files = os.listdir(saved_directory)

    saved_paths = []
    for msg_id in cloudmap:
        file_name = os.path.basename(cloudmap[msg_id]["file_path"])
        file_size = cloudmap[msg_id]["file_size"]

        if file_name in excluded_files:
            continue
        if any(file_name.endswith(suffix) for suffix in excluded_file_suffixes):
            continue
        if not file_size <= max_size:
            continue
        if not filter_name_func(file_name):
            continue

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

        # Check if the file is already pulled at the end
        # since we need the name with msg_id + time of multiple pushed file
        if file_name in pulled_files:
            continue

        saved_path = os.path.join(saved_directory, file_name)
        saved_paths.append(
            {"msg_id": msg_id, "file_size": file_size, "saved_path": saved_path}
        )

    return saved_paths


async def pull_data(client: TelegramClient, symmetric_key, config: Config):
    cloud_channel = await client.get_entity(get_cloud_channel_id())

    if config.target_path["is_file"]:
        file = {}
        # get the lastest file
        reversed_cloudmap = dict(reversed(get_cloudmap().items()))
        for msg_id in reversed_cloudmap:
            file_name = os.path.basename(reversed_cloudmap[msg_id]["file_path"])
            if file_name == os.path.basename(config.target_path["value"]):
                file["msg_id"] = msg_id
                file["file_size"] = reversed_cloudmap[msg_id]["file_size"]
                file["saved_path"] = os.path.abspath(file_name)
                try:
                    result = await _download_file(
                        client, cloud_channel, symmetric_key, file, is_single_file=True
                    )
                    print(
                        f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pulled{Fore.RESET}   {result}"
                    )
                    return
                except asyncio.exceptions.CancelledError:
                    return
        # file name not found
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET}  Pushed file not found"
        )

    else:
        prepared_data = _prepare_pulled_data(
            saved_directory=config.target_path["value"],
            excluded_files=config.excluded_files,
            excluded_file_suffixes=config.excluded_file_suffixes,
            max_size=config.max_size,
            filter_name_func=config.filter_name_func,
        )
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
                f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pulled{Fore.RESET} {str(count).zfill(len(str(len(tasks))))}/{len(tasks)}   {result}"
            )
