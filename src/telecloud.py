import os
import asyncio
import json
import threading
import time
import base64

from colorama import Style, Fore
from telethon import TelegramClient

from . import aes
from .protector import encrypt_file, decrypt_file
from .cloudmapmanager import get_cloudmap, get_salt_from_cloudmap, update_cloudmap

# 6 upload/retrieve files at the time
SEMAPHORE = asyncio.Semaphore(6)


async def upload_file(client: TelegramClient, key, file_path):
    async with SEMAPHORE:
        file_name_hash = {}
        file_encryption_thread = threading.Thread(target=encrypt_file, args=(key, file_name_hash, file_path))
        file_encryption_thread.start()

        while file_encryption_thread.is_alive():
            await asyncio.sleep(0.5)

        file = await client.upload_file(file_name_hash['file_name_hash'])
        msg = await client.send_file('me', file)

        return {
            'success': True,
            'attrib': {
                'msg_id': msg.id,
                'file_name': os.path.basename(file_path),
                'file_name_hash': file_name_hash['file_name_hash'],
                'file_path': os.path.abspath(file_path)
            }
        }

async def download_file(client: TelegramClient, key, msg_id, saved_path):
    async with SEMAPHORE:
        msg = await client.get_messages('me', ids=int(msg_id))
        file_name_hash = msg.document.attributes[0].file_name
        await client.download_file(msg.document, file=file_name_hash)

        file_decryption_thread = threading.Thread(target=decrypt_file, args=(key, file_name_hash, saved_path))
        file_decryption_thread.start()

        while file_decryption_thread.is_alive():
            await asyncio.sleep(0.5)

        return {
            'success': True,
            'file_name_hash': file_name_hash,
            'file_path': saved_path
        }

async def push_data(client: TelegramClient, upload_directory, password):
    new_cloudmap = {}

    salt = get_salt_from_cloudmap()
    symmetric_key = aes.generate_key(password, salt)

    tasks = []
    for dir_path, _, file_names in os.walk(upload_directory):
        for file_name in file_names:
            file_path = os.path.join(dir_path, file_name)
            tasks.append(upload_file(client, symmetric_key, file_path))

    count = 0
    for task in asyncio.as_completed(tasks):
        result = await task

        if result['success']:
            new_cloudmap[result['attrib']['msg_id']] = result['attrib']

            count += 1
            print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RESET} Pushed{Style.RESET_ALL} {str(count).zfill(len(str(len(tasks))))}/{len(tasks)}   {result['attrib']['file_path']}')

        if os.path.exists(result['attrib']['file_name_hash']):
            os.remove(result['attrib']['file_name_hash'])

    update_cloudmap(new_cloudmap)

async def pull_data(client: TelegramClient, saved_directory, password):
    cloudmap = get_cloudmap()

    salt = get_salt_from_cloudmap()
    symmetric_key = aes.generate_key(password, salt)

    tasks = []
    for msg_id in cloudmap:
        saved_path = os.path.join(saved_directory, cloudmap[msg_id]['file_name'])
        tasks.append(download_file(client, symmetric_key, msg_id, saved_path))

    count = 0
    for task in asyncio.as_completed(tasks):
        result = await task
        if result['success']:
            os.remove(result['file_name_hash'])

            count += 1
            print(f'{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RESET} Pulled{Style.RESET_ALL} {str(count).zfill(len(str(len(tasks))))}/{len(tasks)}   {result['file_path']}')

