import os
import asyncio
import threading
import time
from zipfile import ZipFile

from colorama import Fore
from telethon import TelegramClient

from ._data_preparer import PushedDataPreparer
from ..config_manager.config import Config
from ..protector import encrypt_file
from ..constants import CHUNK_LENGTH_FOR_LARGE_FILE, PREPARED_DATA_PATH_FOR_PUSHING
from ..config_manager.config_loader import get_cloud_channel_id
from ..cloudmap import update_cloudmap
from ..utils import (
    logging,
    async_get_checksum,
    get_random_number,
    write_file,
    read_file_in_chunk,
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
        part_num = 1

        for encrypted_chunk in read_file_in_chunk(file_path, is_encrypted=True):
            file_part = os.path.join(
                PREPARED_DATA_PATH_FOR_PUSHING,
                str(part_num) + "_" + os.path.basename(file_path),
            )
            write_file(file_part, encrypted_chunk)

            file_parts.append(file_part)
            part_num += 1

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
        PREPARED_DATA_PATH_FOR_PUSHING, "0_" + os.path.basename(file_path)
    )
    await asyncio.to_thread(write_file, upload_info_path, upload_info, "w", True)
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
        logging(f"{Fore.YELLOW}Pushing{Fore.RESET}  {file_path}")

        # checksum is now the name of encrypted file -> prevent long file name from reaching over 255 chars
        # adding random number to prevent checksum name conflict > two different files could have the same data
        checksum = await async_get_checksum(file_path)
        encrypted_file_path = os.path.join(
            PREPARED_DATA_PATH_FOR_PUSHING,
            # take the first 15 chars since somehow Telegram sometimes cuts the file name
            get_random_number() + "_" + checksum[:15],
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
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "file_size": file_size,
            "checksum": checksum,
            "time": time.strftime("%d-%m-%y.%H-%M-%S"),
        }


async def _zip_file(dir_path, zip_file, file_paths):
    def zip():
        with ZipFile(zip_file, "w") as zip:
            for file in file_paths:
                zip.write(
                    file,
                    arcname=os.path.relpath(file, start=dir_path),
                )

    await asyncio.to_thread(zip)


async def push_data(client: TelegramClient, symmetric_key, config: Config):
    channel_id = get_cloud_channel_id()
    cloud_channel = await client.get_entity(channel_id)

    if config.target_path["is_file"]:
        try:
            result = await _upload_file(
                client,
                cloud_channel,
                symmetric_key,
                config.target_path["value"],
                is_single_file=True,
            )

            result["channel_id"] = channel_id
            await update_cloudmap(result)

            logging(f"{Fore.GREEN}Pushed{Fore.RESET}   {result['file_path']}")

        except asyncio.exceptions.CancelledError:
            return

    else:
        prepared_data = PushedDataPreparer(
            root_directory=config.target_path["value"],
            excluded_dirs=config.excluded_dirs,
            excluded_files=config.excluded_files,
            excluded_file_suffixes=config.excluded_file_suffixes,
            max_size=config.max_size,
            in_name=config.in_name,
            is_recursive=config.is_recursive,
        ).prepare()

        if config.zip_file:
            try:
                zip_name = os.path.basename(config.target_path["value"]) + ".zip"
                zip_file = os.path.join(PREPARED_DATA_PATH_FOR_PUSHING, zip_name)
                logging(f"{Fore.YELLOW}Zipping{Fore.RESET}  {zip_name}")

                await _zip_file(config.target_path["value"], zip_file, prepared_data)
                logging(f"{Fore.GREEN}Zipped{Fore.RESET}   {zip_name}")

                result = await _upload_file(
                    client,
                    cloud_channel,
                    symmetric_key,
                    zip_file,
                    is_single_file=True,
                )

                result["channel_id"] = channel_id
                await update_cloudmap(result)

                os.remove(zip_file)

                logging(f"{Fore.GREEN}Pushed{Fore.RESET}   {result['file_path']}")

            except asyncio.exceptions.CancelledError:
                return

        else:
            tasks = [
                _upload_file(client, cloud_channel, symmetric_key, file_path)
                for file_path in prepared_data
            ]

            count = 0
            for task in asyncio.as_completed(tasks):
                try:
                    result = await task
                    result["channel_id"] = channel_id
                    await update_cloudmap(result)

                    count += 1
                    logging(
                        f"{Fore.GREEN}Pushed{Fore.RESET} {str(count).zfill(len(str(len(tasks))))}/{len(tasks)}   {result['file_path']}"
                    )
                except asyncio.exceptions.CancelledError:
                    # This exception raises when pressing Ctrl+C to stop the program
                    # which cancels all the coros -> return to stop immediately (no need to iterate the rest)
                    return
