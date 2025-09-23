import os
import asyncio
import threading
import time

from colorama import Style, Fore
from telethon import TelegramClient

from .protector import encrypt_file, decrypt_file
from .utils import get_checksum, get_random_number
from .elements import NAMING_FILE_MAX_LENGTH
from .cloudmapmanager import (
    get_cloudmap,
    update_cloudmap,
    get_existed_checksums,
    get_existed_file_names_on_cloudmap,
    get_existed_file_paths_on_cloudmap
)

# 6 upload/retrieve files at the time
SEMAPHORE = asyncio.Semaphore(6)


async def _upload_file(client: TelegramClient, key, file_path):
    async with SEMAPHORE:
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
        encrypted_file_path = get_random_number() + '_' + checksum

        # encrypt file before uploading to cloud
        encryption_process_future = loop.create_future()
        file_encryption_thread = threading.Thread(
            target=encrypt_file, args=(key, file_path, encrypted_file_path, loop, encryption_process_future)
        )
        file_encryption_thread.start()

        await encryption_process_future

        file = await client.upload_file(encrypted_file_path, file_name=encrypted_file_path)
        msg = await client.send_file('me', file)

        return {
            'success': True,
            'msg_id': msg.id,
            'encrypted_file_path': encrypted_file_path,
            'attrib': {
                'checksum': checksum,
                'file_path': file_path,
                'time': time.strftime('%d-%m-%y %H|%M|%S')
            }
        }

def _prepare_pushed_data(upload_directory):
    existed_file_paths = get_existed_file_paths_on_cloudmap()
    checksums = get_existed_checksums()

    file_paths = []
    for dir_path, _, file_names in os.walk(upload_directory):
        for file_name in file_names:
            file_path = os.path.abspath(os.path.join(dir_path, file_name))

            if file_path not in existed_file_paths:
                file_paths.append(file_path)
                continue

            if get_checksum(file_path, None, None, is_holder=False) not in checksums:
                file_paths.append(file_path)
                continue

            print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Remained{Style.RESET_ALL}   {file_path}')

    return file_paths

async def push_data(client: TelegramClient, encryption_key, upload_directory):
    new_cloudmap = get_cloudmap()

    prepared_data = _prepare_pushed_data(upload_directory)
    tasks = [_upload_file(client, encryption_key, file_path) for file_path in prepared_data]

    count = 0
    for task in asyncio.as_completed(tasks):
        result = await task
        if result['success']:
            new_cloudmap[result['msg_id']] = result['attrib']

            count += 1
            print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pushed{Style.RESET_ALL} {str(count).zfill(len(str(len(tasks))))}/{len(tasks)}   {result['attrib']['file_path']}')

            os.remove(result['encrypted_file_path'])

    update_cloudmap(new_cloudmap)

async def _download_file(client: TelegramClient, key, msg_id, saved_path):
    async with SEMAPHORE:
        msg = await client.get_messages('me', ids=int(msg_id))
        checksum = msg.document.attributes[0].file_name
        encrypted_file_from_cloud = saved_path.replace(os.path.basename(saved_path), checksum)
        await client.download_file(msg.document, file=encrypted_file_from_cloud)

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        file_decryption_thread = threading.Thread(
            target=decrypt_file, args=(key, encrypted_file_from_cloud, saved_path, loop, future)
        )
        file_decryption_thread.start()

        # result of the decryption process success or failed
        result = await future
        result['file_path'] = saved_path
        result['encrypted_file_from_cloud'] = encrypted_file_from_cloud
        return result

def _prepare_pulled_data(saved_directory):
    cloudmap = get_cloudmap()
    existed_file_names = get_existed_file_names_on_cloudmap()

    saved_paths = []
    for msg_id in cloudmap:
        file_name = os.path.basename(cloudmap[msg_id]['file_path'])

        # If a file has multiple uploads, when downloading we need to make its name different with time
        # since it shares the same name
        if existed_file_names.count(file_name) != 1:
            differentor = '.' + msg_id + '.' + cloudmap[msg_id]['time']
            base, ext = os.path.splitext(file_name)
            new_file_name = base + differentor + ext

            if len(new_file_name) > NAMING_FILE_MAX_LENGTH:
                # prevent filename reaches the limit (255 chars)
                file_name = base[:-(len(differentor) + len(ext))] + differentor + ext
            else:
                file_name = new_file_name

        saved_path = os.path.abspath(os.path.join(saved_directory, file_name))
        saved_paths.append(
            {
                'msg_id': msg_id,
                'saved_path': saved_path
            }
        )

    return saved_paths

async def pull_data(client: TelegramClient, decryption_key, saved_directory):
    prepared_data = _prepare_pulled_data(saved_directory)
    tasks = [
        _download_file(client, decryption_key, data['msg_id'], data['saved_path']) for data in prepared_data
    ]

    count = 0
    for task in asyncio.as_completed(tasks):
        result = await task
        os.remove(result['encrypted_file_from_cloud'])

        if result['success']:
            count += 1
            print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pulled{Style.RESET_ALL} {str(count).zfill(len(str(len(tasks))))}/{len(tasks)}   {result['file_path'][:-10]}')
        else:
            print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}  {Fore.RED}{result['error']}{Fore.RESET}   {result['file_path'][:-10]}')

