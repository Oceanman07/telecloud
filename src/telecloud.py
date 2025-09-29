import json
import os
import asyncio
import threading
import time

from colorama import Style, Fore
from telethon import TelegramClient

from .protector import encrypt_file, decrypt_file
from .elements import FILE_PART_LENGTH_FOR_LARGE_FILE, KEY_TEST_PATH, NAMING_FILE_MAX_LENGTH
from .utils import (
    get_checksum,
    get_random_number,
    write_file,
    read_file_in_chunk
)
from .cloudmapmanager import (
    get_cloud_channel_id,
    get_cloudmap,
    update_cloudmap,
    get_existed_checksums,
    get_existed_file_names_on_cloudmap,
    get_existed_file_paths_on_cloudmap
)

# 8 upload/retrieve files at the time
SEMAPHORE = asyncio.Semaphore(8)


async def _upload_small_file(client: TelegramClient, cloud_channel, file_path):
    progress_upload = lambda sent, total: print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.YELLOW} Pushing{Style.RESET_ALL} {file_path}:{Style.BRIGHT}{sent/total:.0%}{Style.RESET_ALL}')

    file = await client.upload_file(file_path, file_name=file_path, part_size_kb=512, progress_callback=progress_upload)
    msg = await client.send_file(cloud_channel, file)
    os.remove(file_path)

    return msg.id

def _split_big_file(file_path, loop: asyncio.AbstractEventLoop, future: asyncio.Future):
    max_split_times = 7
    split_count = 0
    part_num = 1
    file_parts = []
    written_size = 0

    size_file = os.path.getsize(file_path)
    for encrypted_chunk in read_file_in_chunk(file_path, is_encrypted=True):
        file_part = file_path + '-' + str(part_num)
        with open(file_part, 'ab') as f:
            f.write(encrypted_chunk)
            written_size += len(encrypted_chunk)

        split_count += 1
        if split_count == max_split_times:
            part_num += 1
            file_parts.append(file_part)
            split_count = 0

        elif written_size >= size_file:
            file_parts.append(file_part)

    loop.call_soon_threadsafe(future.set_result, file_parts)

async def _upload_big_file(client: TelegramClient, cloud_channel, file_path):
    semaphore = asyncio.Semaphore(3)

    async def upload(file_part):
        async with semaphore:
            progress_upload = lambda sent, total: print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.YELLOW} Pushing{Style.RESET_ALL} {file_part}:{Style.BRIGHT}{sent/total:.0%}{Style.RESET_ALL}')
            file = await client.upload_file(file_part, file_name=file_part, part_size_kb=512, progress_callback=progress_upload)
            msg = await client.send_file(cloud_channel, file)
            os.remove(file_part)

            return {file_part: msg.id}

    loop = asyncio.get_running_loop()
    file_parts_value_future = loop.create_future()

    split_big_file_thread = threading.Thread(
        target=_split_big_file, args=(file_path, loop, file_parts_value_future)
    )
    split_big_file_thread.start()

    file_parts = await file_parts_value_future
    os.remove(file_path)

    upload_info = {
        'num': len(file_parts),
        'parts': {}
    }
    upload_info_path = file_path + '-0'

    tasks = [upload(file) for file in file_parts]
    for task in asyncio.as_completed(tasks):
        msg_id = await task
        upload_info['parts'].update(msg_id)

    await loop.run_in_executor(None, write_file, upload_info_path, json.dumps(upload_info), 'w')
    msg = await upload(upload_info_path)

    return msg[upload_info_path]

async def _upload_file(client: TelegramClient, cloud_channel, symmetric_key, file_path):
    async with SEMAPHORE:
        print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pushing{Style.RESET_ALL} {file_path}')

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
            target=encrypt_file, args=(symmetric_key, file_path, encrypted_file_path, loop, encryption_process_future)
        )
        file_encryption_thread.start()

        await encryption_process_future

        file_size = os.path.getsize(file_path)
        if file_size < FILE_PART_LENGTH_FOR_LARGE_FILE:
            msg_id = await _upload_small_file(client, cloud_channel, encrypted_file_path)
        else:
            msg_id = await _upload_big_file(client, cloud_channel, encrypted_file_path)

        return {
            'success': True,
            'msg_id': msg_id,
            'attrib': {
                'checksum': checksum,
                'file_path': file_path,
                'file_size': file_size,
                'time': time.strftime('%d-%m-%y.%H-%M-%S')
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

async def _encrypt_key_test(symmetric_key):
    write_file(
        KEY_TEST_PATH,
        'detect if the symmetric key is valid or not, if not then no need to start pulling files',
        mode='w'
    )

    loop = asyncio.get_running_loop()
    future = loop.create_future()

    thread = threading.Thread(
        target=encrypt_file, args=(symmetric_key, KEY_TEST_PATH, KEY_TEST_PATH, loop, future)
    )
    thread.start()

    await future

async def push_data(client: TelegramClient, symmetric_key, upload_directory):
    # decrypt key_test first to ensure the key (password) remains the same
    key_test_result = await _decrypt_key_test(symmetric_key)
    if not key_test_result['success']:
        print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}{Fore.RED} - Password does not match{Style.RESET_ALL}')
        return

    await _encrypt_key_test(symmetric_key)

    new_cloudmap = get_cloudmap()

    cloud_channel = await client.get_entity(get_cloud_channel_id())
    prepared_data = _prepare_pushed_data(upload_directory)
    tasks = [_upload_file(client, cloud_channel, symmetric_key, file_path) for file_path in prepared_data]

    count = 0
    for task in asyncio.as_completed(tasks):
        result = await task
        if result['success']:
            new_cloudmap[result['msg_id']] = result['attrib']

            count += 1
            print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pushed{Style.RESET_ALL} {str(count).zfill(len(str(len(tasks))))}/{len(tasks)}   {result['attrib']['file_path']}')

    update_cloudmap(new_cloudmap)

async def _download_file(client: TelegramClient, cloud_channel, symmetric_key, msg_id, saved_path):
    async with SEMAPHORE:
        print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pulling{Style.RESET_ALL} {saved_path}')

        msg = await client.get_messages(cloud_channel, ids=int(msg_id))
        file_from_cloud = msg.document.attributes[0].file_name
        await client.download_file(msg.document, file=file_from_cloud, part_size_kb=512)

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        file_decryption_thread = threading.Thread(
            target=decrypt_file, args=(symmetric_key, file_from_cloud, saved_path, loop, future)
        )
        file_decryption_thread.start()

        # result of the decryption process success or failed
        result = await future
        result['file_path'] = saved_path

        os.remove(file_from_cloud)

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

async def _decrypt_key_test(symmetric_key):
    """
    test the symmetric_key to see if its valid or not, if not then stop
    """
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    thread = threading.Thread(
        target=decrypt_file, args=(symmetric_key, KEY_TEST_PATH, KEY_TEST_PATH, loop, future)
    )
    thread.start()

    return await future

async def pull_data(client: TelegramClient, symmetric_key, saved_directory):
    key_test_result = await _decrypt_key_test(symmetric_key)
    if not key_test_result['success']:
        print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}{Fore.RED} - {key_test_result['error']}{Style.RESET_ALL}')
        return

    await _encrypt_key_test(symmetric_key)

    cloud_channel = await client.get_entity(get_cloud_channel_id())
    prepared_data = _prepare_pulled_data(saved_directory)
    tasks = [_download_file(client, cloud_channel, symmetric_key, data['msg_id'], data['saved_path']) for data in prepared_data]

    count = 0
    for task in asyncio.as_completed(tasks):
        result = await task

        count += 1
        print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Pulled{Style.RESET_ALL} {str(count).zfill(len(str(len(tasks))))}/{len(tasks)}   {result['file_path']}')

