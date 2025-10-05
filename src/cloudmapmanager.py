import os
import json
import base64
import io
import time
from getpass import getpass

from colorama import Style, Fore
from telethon import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest, EditPhotoRequest
from telethon.tl.types import InputChatUploadedPhoto

from .aes import generate_key
from .logo import LOGO
from .protector import encrypt_string_session
from .utils import read_file, write_file
from .constants import (
    CONFIG_PATH,
    CLOUDMAP_PATH,
    STRING_SESSION_PATH,
    INCLUDED_CLOUDMAP_PATHS,
    STORED_PREPARED_FILE_PATHS,
)


async def setup_cloudmap(client: TelegramClient, session, api_id, api_hash):
    # This step is the very first step
    # -> write_file doesnt need to be async since the blocking doesnt affect at all

    # encrypted files before uploading or decrypting will be stored here
    os.makedirs(STORED_PREPARED_FILE_PATHS, exist_ok=True)

    # setup password
    print(
        f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Setup password:{Style.RESET_ALL}"
    )
    print(
        f"Remember! {Style.BRIGHT}One password{Style.RESET_ALL} to rule them all, {Style.BRIGHT}One Password{Style.RESET_ALL} to find them, {Style.BRIGHT}One Password{Style.RESET_ALL} to bring them all, and in case you forget you might {Style.BRIGHT}lose{Style.RESET_ALL} them all. So, choose wisely!"
    )
    password = input(">: ")
    repeated = getpass("Confirm:\n>: ")
    if password != repeated:
        print(
            f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Password does not match{Style.RESET_ALL}"
        )
        exit()

    # salt + password to generate key
    salt = os.urandom(32)

    symmetric_key = generate_key(password, salt)
    write_file(STRING_SESSION_PATH, session, mode="w")
    await encrypt_string_session(symmetric_key)

    # cloudmap stores file info -> msg_id, checksum, file_path, file_size, time
    cloudmap = {}
    write_file(CLOUDMAP_PATH, json.dumps(cloudmap), mode="w")

    # create cloud channel to store files
    channel_id = await _create_channel(client)
    print(
        f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Style.RESET_ALL} Created cloud channel with ID:{channel_id}"
    )

    config = {
        "api_id": api_id,
        "api_hash": api_hash,
        "salt": base64.b64encode(salt).decode(),
        "cloud_channel_id": int(
            "-100" + str(channel_id)
        ),  # PeerChannel → -100 + channel ID
    }
    write_file(CONFIG_PATH, json.dumps(config), mode="w")

    await _set_channel_photo(client)


def check_health_cloudmap():
    return all(os.path.exists(path) for path in INCLUDED_CLOUDMAP_PATHS)


async def _set_channel_photo(client: TelegramClient):
    # This is also the very first step
    # -> decoding doesnt need to be async since the blocking doesnt affect at all
    file_bytes = io.BytesIO(base64.b64decode(LOGO))
    file_bytes.name = "CloudLogoAvatar.png"

    uploaded_file = await client.upload_file(file_bytes)
    chat_photo = InputChatUploadedPhoto(uploaded_file)
    channel = await client.get_entity(get_cloud_channel_id())

    await client(EditPhotoRequest(channel, chat_photo))


async def _create_channel(client: TelegramClient):
    channel = await client(
        CreateChannelRequest(title="TeleCloud", about="Free cloud", megagroup=False)
    )
    return channel.chats[0].id


def update_cloudmap(cloudmap):
    write_file(CLOUDMAP_PATH, json.dumps(cloudmap, ensure_ascii=False), mode="w")


def get_cloudmap():
    return json.loads(read_file(CLOUDMAP_PATH))


def get_cloud_channel_id():
    config = json.loads(read_file(CONFIG_PATH))
    return config["cloud_channel_id"]


def get_salt_from_cloudmap():
    config = json.loads(read_file(CONFIG_PATH))
    return base64.b64decode(config["salt"])


def get_api_id():
    config = json.loads(read_file(CONFIG_PATH))
    return config["api_id"]


def get_api_hash():
    config = json.loads(read_file(CONFIG_PATH))
    return config["api_hash"]


def get_existed_file_paths_on_cloudmap():
    cloudmap = get_cloudmap()
    return [cloudmap[msg_id]["file_path"] for msg_id in cloudmap]


def get_existed_file_names_on_cloudmap():
    """
    Get all the file names of pushed files for naming pulled files
    it cannot use `set` to deduplicate for smaller size
    since a single file has multiple uploads means it has changed a lot
    so when pulling we will have all the changed version of that file with file name = file_name + msg_id + time
    """
    cloudmap = get_cloudmap()
    return [os.path.basename(cloudmap[msg_id]["file_path"]) for msg_id in cloudmap]


def get_existed_checksums():
    """
    Get all the checksums of pushed files for checking if a file is changed or not
    if it doesnt change then no need to push again
    a lot of files may have the same content so use `set` to deduplicate for faster checking
    """
    cloudmap = get_cloudmap()
    return set([cloudmap[msg_id]["checksum"] for msg_id in cloudmap])


def clean_prepared_data():
    for path in os.listdir(STORED_PREPARED_FILE_PATHS):
        file_path = os.path.join(STORED_PREPARED_FILE_PATHS, path)
        os.remove(file_path)
