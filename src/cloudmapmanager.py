import os
import json
import base64
import time
from getpass import getpass

from colorama import Style, Fore
from telethon import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest, EditPhotoRequest
from telethon.tl.types import InputChatUploadedPhoto

from .aes import generate_key
from .protector import encrypt_file

from .utils import read_file, write_file
from .elements import (
    LOGO_PATH,
    SALT_PATH,
    KEY_TEST_PATH,
    CLOUDMAP_PATH,
    STORED_CLOUDMAP_PATHS,
    CLOUD_CHANNEL_ID_PATH,
    INCLUDED_CLOUDMAP_PATHS,
)


async def setup_cloudmap(client: TelegramClient):
    # this is the very first step -> write_file doesnt need to by async since the blocking doesn affect at all
    os.makedirs(STORED_CLOUDMAP_PATHS, exist_ok=True)

    # cloudmap stores file info -> msg_id, checksum, file_path, time
    cloudmap = {}
    write_file(CLOUDMAP_PATH, json.dumps(cloudmap), mode="w")

    # salt + password to generate key
    salt = os.urandom(32)
    write_file(SALT_PATH, base64.b64encode(salt).decode(), mode="w")

    # files will be uploaded in this channel
    if not os.path.exists(CLOUD_CHANNEL_ID_PATH):
        channel_id = await _create_channel(client)
        write_file(CLOUD_CHANNEL_ID_PATH, str(channel_id), mode="w")
        await _set_channel_photo(client)

    # a string for testing key
    write_file(
        KEY_TEST_PATH,
        "detect if the symmetric key is valid or not, if not then no need to start pulling files",
        mode="w",
    )

    # setup password
    print(
        f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Setup password:{Style.RESET_ALL}"
    )
    print(
        f"Remember! {Style.BRIGHT}One password{Style.RESET_ALL} to rule them all, {Style.BRIGHT}One Password{Style.RESET_ALL} to find them, {Style.BRIGHT}One Password{Style.RESET_ALL} to bring them all, and in case you forget you might {Style.BRIGHT}lose{Style.RESET_ALL} them all. So, choose wisely!"
    )
    password = input(">_ ")
    repeated = getpass("Confirm:\n>_ ")

    if password != repeated:
        print(
            f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Password does not match{Style.RESET_ALL}"
        )
        os.remove(SALT_PATH)
        os.remove(KEY_TEST_PATH)
        exit()

    symmetric_key = generate_key(password, salt)
    encrypt_file(symmetric_key, KEY_TEST_PATH, KEY_TEST_PATH, None, None)


def check_health_cloudmap():
    return all(os.path.exists(path) for path in INCLUDED_CLOUDMAP_PATHS)


async def _set_channel_photo(client: TelegramClient):
    file = await client.upload_file(LOGO_PATH)
    chat_photo = InputChatUploadedPhoto(file)
    channel = await client.get_entity(get_cloud_channel_id())

    await client(EditPhotoRequest(channel, chat_photo))


async def _create_channel(client: TelegramClient):
    channel = await client(
        CreateChannelRequest(title="TeleCloud", about="Free cloud", megagroup=False)
    )
    return channel.chats[0].id


def get_cloud_channel_id():
    return int(read_file(CLOUD_CHANNEL_ID_PATH))


def update_cloudmap(cloudmap):
    write_file(CLOUDMAP_PATH, json.dumps(cloudmap, ensure_ascii=False), mode="w")


def get_cloudmap():
    return json.loads(read_file(CLOUDMAP_PATH))


def get_salt_from_cloudmap():
    salt = read_file(SALT_PATH)
    return base64.b64decode(salt)


def get_existed_file_paths_on_cloudmap():
    cloudmap = get_cloudmap()
    return [cloudmap[msg_id]["file_path"] for msg_id in cloudmap]


def get_existed_file_names_on_cloudmap():
    cloudmap = get_cloudmap()
    return [os.path.basename(cloudmap[msg_id]["file_path"]) for msg_id in cloudmap]


def get_existed_checksums():
    cloudmap = get_cloudmap()
    return [cloudmap[msg_id]["checksum"] for msg_id in cloudmap]
