import os
import hashlib
import asyncio
import threading

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.tlobject import base64

from src import aes

SEMAPHORE = asyncio.Semaphore(4)

load_dotenv()
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']


async def inspect_tasks():
    # keep printing tasks every 0.2s
    while True:
        tasks = [t for t in asyncio.all_tasks() if not t.done()]
        active = [str(t.get_coro()) for t in tasks]
        print(len(active))
        await asyncio.sleep(0.2)

def encrypt_file(key, file_path, info: dict):
    with open(file_path, 'rb') as f:
        file_content = f.read()
    encrypted_data = aes.encrypt(key, file_content)

    info['file_name_hash'] = hashlib.sha1(file_path.encode()).hexdigest()
    with open(info['file_name_hash'], 'wb') as f:
        f.write(encrypted_data)

async def upload_file(client: TelegramClient, key, file_path):
    async with SEMAPHORE:
        info = {}
        file_encryption_thread = threading.Thread(target=encrypt_file, args=(key, file_path, info))
        file_encryption_thread.start()

        while file_encryption_thread.is_alive():
            await asyncio.sleep(0.5)

        file = await client.upload_file(
            info['file_name_hash'],
            progress_callback=lambda sent, total: print(f'{file_path} - {sent/total:.0%}')
        )
        await client.send_file('me', file)

        os.remove(info['file_name_hash'])
        return f'Uploaded to cloud: {file_path}'

async def iter_msgs(client: TelegramClient):
    async for msg in client.iter_messages('me'):
        print(msg)

async def send_message(client: TelegramClient, msg):
    await client.send_message('me', msg)

async def main():
    password = 'Password'
    salt = os.urandom(32)
    symmetric_key = aes.generate_key(password, salt)

    dir_path = './data'
    async with TelegramClient('Cloud', api_id=api_id, api_hash=api_hash) as client:
        await send_message(client, '———————————————————————————————————————————')
        await send_message(client, f'salt: {base64.b64encode(salt).decode()}')

        tasks = [upload_file(client, symmetric_key, os.path.join(dir_path, path)) for path in os.listdir(dir_path)]

        for task in asyncio.as_completed(tasks):
            result = await task
            print(result)

if __name__ == '__main__':
    asyncio.run(main())

