import os
import hashlib
import asyncio
import threading
import json
import base64

from dotenv import load_dotenv
from telethon import TelegramClient

from src.parser import parse_args
from src import aes

SEMAPHORE = asyncio.Semaphore(4)

load_dotenv()
api_id = int(os.environ['API_ID'])
api_hash = os.environ['API_HASH']


async def iter_msgs(client: TelegramClient):
    async for msg in client.iter_messages('me'):
        if msg.document:
            print(f'{msg.document.attributes[0].file_name} : {msg.document.size}')

async def delete_msgs(client: TelegramClient):
    async for msg in client.iter_messages('me'):
        await client.delete_messages('me', msg.id)

def encrypt_file(key, file_name_hash, file_path):
    with open(file_path, 'rb') as f:
        file_content = f.read()
    encrypted_data = aes.encrypt(key, file_content)

    file_name_hash['file_name_hash'] = hashlib.sha1(file_path.encode()).hexdigest()
    with open(file_name_hash['file_name_hash'], 'wb') as f:
        f.write(encrypted_data)

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

def decrypt_file(key, file_name_hash, file_path):
    with open(file_name_hash, 'rb') as f:
        encrypted_data = f.read()
    original_data = aes.decrypt(key, encrypted_data)

    with open(file_path, 'wb') as f:
        f.write(original_data)

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
    salt = os.urandom(32)
    symmetric_key = aes.generate_key(password, salt)

    uploads_info = {
    'salt': base64.b64encode(salt).decode(),
        'uploads': {}
    }

    file_paths = []
    for dir_path, _, file_names in os.walk(upload_directory):
        for file_name in file_names:
            file_paths.append(os.path.join(dir_path, file_name))

    tasks = [upload_file(client, symmetric_key, file_path) for file_path in file_paths]
    for task in asyncio.as_completed(tasks):
        result = await task
        if result['success']:
            uploads_info['uploads'][result['attrib']['msg_id']] = result['attrib']
            print(f"Uploaded to cloud: {result['attrib']['file_path']}")
            os.remove(result['attrib']['file_name_hash'])

    with open('uploads.json', 'w') as f:
        f.write(json.dumps(uploads_info, ensure_ascii=False))

async def pull_data(client: TelegramClient, saved_directory, password):
    with open('./uploads.json', 'r') as f:
        content = json.loads(f.read())

    salt = base64.b64decode(content['salt'])
    symmetric_key = aes.generate_key(password, salt)

    tasks = []
    for msg_id in content['uploads']:
        saved_path = os.path.join(saved_directory, content['uploads'][msg_id]['file_name'])
        tasks.append(download_file(client, symmetric_key, msg_id, saved_path))

    for task in asyncio.as_completed(tasks):
        result = await task
        os.remove(result['file_name_hash'])
        print(result['success'], ' - ', result['file_path'])

async def main():
    args = parse_args()

    async with TelegramClient('Cloud', api_id=api_id, api_hash=api_hash) as client:
        # await delete_msgs(client)

        if args.push:
            await push_data(client, args.directory, args.password)

        elif args.pull:
            await pull_data(client, args.directory, args.password)

if __name__ == '__main__':
    asyncio.run(main())

