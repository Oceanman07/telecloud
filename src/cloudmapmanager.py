import os
import asyncio
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
from .protector import encrypt_file
from .utils import read_file, write_file
from .constants import (
    CONFIG_PATH,
    CLOUDMAP_PATH,
    STRING_SESSION_PATH,
    STORED_CLOUDMAP_PATHS,
    INCLUDED_CLOUDMAP_PATHS,
    STORED_PREPARED_FILE_PATHS,
)


async def setup_cloudmap(client: TelegramClient, session, api_id, api_hash):
    # This step is the very first step
    # -> write_file doesnt need to be async since the blocking doesnt affect at all

    # the container
    os.makedirs(STORED_CLOUDMAP_PATHS, exist_ok=True)

    # encrypted files before uploading or decrypting will be stored here
    os.makedirs(STORED_PREPARED_FILE_PATHS, exist_ok=True)

    # configure default pulled directory
    home_dir = os.path.expanduser("~")
    pulled_dir_in_desktop = os.path.join(
        home_dir, os.path.join("Desktop", "TeleCloudFiles")
    )
    pulled_dir_in_documents = os.path.join(
        home_dir, os.path.join("Documents", "TeleCloudFiles")
    )
    pulled_dir_in_downloads = os.path.join(
        home_dir, os.path.join("Downloads", "TeleCloudFiles")
    )
    print(
        f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Configure your default pulled directory{Fore.RESET}\n"
        f"Your files will be downloaded and stored here if not provided a specific directory when pulling all files"
    )
    print(
        f"[1] {pulled_dir_in_desktop}\n"
        f"[2] {pulled_dir_in_documents}\n"
        f"[3] {pulled_dir_in_downloads}"
    )

    default_pulled_dir = pulled_dir_in_desktop  # default
    while True:
        user_choice = input("Your choice 1/2/3: ")
        if user_choice not in ("1", "2", "3"):
            continue

        if user_choice == "1":
            pass  # desktop is alread the default choice
        elif user_choice == "2":
            default_pulled_dir = pulled_dir_in_documents
        elif user_choice == "3":
            default_pulled_dir = pulled_dir_in_downloads

        os.makedirs(default_pulled_dir, exist_ok=True)
        break

    # configure password
    print(
        f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Configure your password for encrypting/decrypting files{Fore.RESET}\n"
    )
    print(
        f"Remember! {Style.BRIGHT}One password{Style.RESET_ALL} to rule them all, {Style.BRIGHT}One Password{Style.RESET_ALL} to find them, {Style.BRIGHT}One Password{Style.RESET_ALL} to bring them all, and in case you forget you might {Style.BRIGHT}lose{Style.RESET_ALL} them all. So, choose wisely!"
    )
    password = input(">: ")
    repeated = getpass("Confirm:\n>: ")
    if password != repeated:
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET}   Password does not match"
        )
        exit()

    # salt + password to generate key
    salt = os.urandom(32)

    symmetric_key = generate_key(password, salt)
    write_file(STRING_SESSION_PATH, session, mode="w")
    await encrypt_file(symmetric_key, STRING_SESSION_PATH, STRING_SESSION_PATH)

    # cloudmap stores file info -> msg_id, checksum, file_path, file_size, time
    cloudmap = {}
    write_file(CLOUDMAP_PATH, cloudmap, mode="w", serialize=True)

    # create cloud channel to store files
    channel_id = await _create_channel(client)
    print(f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RESET} Cloud channel created")

    config = {
        "api_id": api_id,
        "api_hash": api_hash,
        "cloud_channel_id": int(
            "-100" + str(channel_id)
        ),  # PeerChannel → -100 + channel ID
        "salt": salt.hex(),
        "pulled_directory": default_pulled_dir,
        "is_auto_fill_password": {"status": False, "value": None},
    }
    write_file(CONFIG_PATH, config, mode="w", serialize=True)

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


async def update_cloudmap(cloudmap):
    await asyncio.get_running_loop().run_in_executor(
        None, write_file, CLOUDMAP_PATH, cloudmap, "w", True
    )


def load_config(func):
    config = None
    if os.path.exists(CONFIG_PATH):
        config = read_file(CONFIG_PATH, mode="r", deserialize=True)

    def load():
        nonlocal config
        if config is None:
            config = read_file(CONFIG_PATH, mode="r", deserialize=True)
        return func(config)

    return load


@load_config
def get_api_id(config):
    return config["api_id"]


@load_config
def get_api_hash(config):
    return config["api_hash"]


@load_config
def get_cloud_channel_id(config):
    return config["cloud_channel_id"]


@load_config
def get_salt_from_cloudmap(config):
    return bytes.fromhex(config["salt"])


@load_config
def get_default_pulled_directory(config):
    return config["pulled_directory"]


def load_cloudmap(func):
    cloudmap = None
    if os.path.exists(CLOUDMAP_PATH):
        cloudmap = read_file(CLOUDMAP_PATH, mode="r", deserialize=True)

    def load():
        nonlocal cloudmap
        if cloudmap is None:
            cloudmap = read_file(CLOUDMAP_PATH, mode="r", deserialize=True)
        return func(cloudmap)

    return load


@load_cloudmap
def get_cloudmap(cloudmap):
    return cloudmap


@load_cloudmap
def get_existed_file_names_on_cloudmap(cloudmap):
    """
    Get all the file names of pushed files for naming pulled files
    it cannot use `set` to deduplicate for smaller size
    since a single file has multiple uploads means it has changed a lot
    so when pulling we will have all the changed version of that file with file name = file_name + msg_id + time
    """
    return [os.path.basename(cloudmap[msg_id]["file_path"]) for msg_id in cloudmap]


@load_cloudmap
def get_existed_checksums(cloudmap):
    """
    Get all the checksums of pushed files for checking if a file is changed or not
    if it doesnt change then no need to push again
    a lot of files may have the same content so use `set` to deduplicate for faster checking
    """
    return set([cloudmap[msg_id]["checksum"] for msg_id in cloudmap])


@load_cloudmap
def get_existed_file_paths_on_cloudmap(cloudmap):
    # like get_existed_checksums
    return set([cloudmap[msg_id]["file_path"] for msg_id in cloudmap])


def clean_prepared_data():
    for path in os.listdir(STORED_PREPARED_FILE_PATHS):
        file_path = os.path.join(STORED_PREPARED_FILE_PATHS, path)
        os.remove(file_path)
