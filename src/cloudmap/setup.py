import os
import io
import time
import base64
import sqlite3
from getpass import getpass

from colorama import Style, Fore
from telethon import TelegramClient
from telethon.tl.functions.channels import CreateChannelRequest, EditPhotoRequest
from telethon.tl.types import InputChatUploadedPhoto

from .. import aes, rsa
from ..icon import ICON
from ..utils import write_file
from ..constants import (
    ENCRYPTED_PRIVATE_KEY_PATH,
    PULLED_DIR_IN_DESKTOP,
    PULLED_DIR_IN_DOCUMENTS,
    PULLED_DIR_IN_DOWNLOADS,
    CONFIG_PATH,
    CLOUDMAP_DB_PATH,
    STRING_SESSION_PATH,
    STORED_CLOUDMAP_PATHS,
    INCLUDED_CLOUDMAP_PATHS,
    STORED_PREPARED_FILE_PATHS,
)


def check_health_cloudmap():
    return all(os.path.exists(path) for path in INCLUDED_CLOUDMAP_PATHS)


def _get_default_pulled_directory():
    while True:
        user_choice = input("Your choice 1/2/3: ")
        if user_choice not in ("1", "2", "3"):
            continue

        if user_choice == "1":
            default_pulled_dir = PULLED_DIR_IN_DESKTOP
        elif user_choice == "2":
            default_pulled_dir = PULLED_DIR_IN_DOCUMENTS
        elif user_choice == "3":
            default_pulled_dir = PULLED_DIR_IN_DOWNLOADS

        os.makedirs(default_pulled_dir, exist_ok=True)

        return default_pulled_dir


def _get_password():
    password = input(">: ")
    while True:
        confirm = getpass("Confirm:\n>: ")
        if password != confirm:
            print(
                f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET} - Password does not match"
            )
            continue

        return password


async def create_channel(client: TelegramClient, title="TeleCloud", about="Free cloud"):
    channel = await client(CreateChannelRequest(title, about, megagroup=False))
    channel_id = channel.chats[0].id
    return int("-100" + str(channel_id))  # PeerChannel → -100 + channel ID


async def set_channel_photo(
    client: TelegramClient, cloud_channel_id, file_name="icon.jpg"
):
    file_bytes = io.BytesIO(base64.b64decode(ICON))
    file_bytes.name = file_name

    uploaded_file = await client.upload_file(file_bytes)
    chat_photo = InputChatUploadedPhoto(uploaded_file)
    channel = await client.get_entity(cloud_channel_id)

    await client(EditPhotoRequest(channel, chat_photo))


def create_database():
    conn = sqlite3.connect(CLOUDMAP_DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cloudmap (
            channel_id INTERGER,
            msg_id INTERGER,
            file_path TEXT,
            file_name TEXT,
            file_size INTERGER,
            checksum TEXT,
            time TEXT
        )
        """
    )

    conn.commit()
    conn.close()


async def setup_cloudmap(client: TelegramClient, session, api_id, api_hash):
    # This step is the very first step -> the blocking does not affect at all

    # the container
    os.makedirs(STORED_CLOUDMAP_PATHS, exist_ok=True)

    # encrypted files before uploading or decrypting will be stored here
    os.makedirs(STORED_PREPARED_FILE_PATHS, exist_ok=True)

    # configure default pulled directory
    print(
        f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Configure your default pulled directory{Fore.RESET}\n"
        f"Your files will be downloaded and stored here if not provided a specific directory when pulling all files"
    )
    print(
        f"[1] {PULLED_DIR_IN_DESKTOP}\n"
        f"[2] {PULLED_DIR_IN_DOCUMENTS}\n"
        f"[3] {PULLED_DIR_IN_DOWNLOADS}"
    )
    default_pulled_dir = _get_default_pulled_directory()

    # password for encrypting/decrypting private key
    print(
        f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Configure your password for encrypting/decrypting files{Fore.RESET}"
    )
    print(
        f"Remember! {Style.BRIGHT}One password{Style.RESET_ALL} to rule them all, {Style.BRIGHT}One Password{Style.RESET_ALL} to find them, {Style.BRIGHT}One Password{Style.RESET_ALL} to bring them all, and in case you forget you might {Style.BRIGHT}lose{Style.RESET_ALL} them all. So, choose wisely!"
    )
    password = _get_password()

    # the main symmetric key for encrypting/decrypting StringSession, files
    password_for_main_symmetric_key = os.urandom(32).hex()
    salt_for_main_symmetric_key = os.urandom(32)

    main_symmetric_key = aes.generate_key(
        password_for_main_symmetric_key, salt_for_main_symmetric_key
    )

    encrypted_session = aes.encrypt(main_symmetric_key, session.encode())
    write_file(STRING_SESSION_PATH, encrypted_session)

    # public key, private key for encrypting/decrypting main_symmetric_key
    private_key, public_key = rsa.generate_keys()

    password_for_private_key = password
    salt_for_private_key = os.urandom(32)

    symmetric_key_for_private_key = aes.generate_key(
        password_for_private_key, salt_for_private_key
    )

    encrypted_private_key = aes.encrypt(symmetric_key_for_private_key, private_key)
    write_file(ENCRYPTED_PRIVATE_KEY_PATH, salt_for_private_key)
    write_file(ENCRYPTED_PRIVATE_KEY_PATH, encrypted_private_key, mode="ab")

    encrypted_main_symmetric_key = rsa.encrypt(public_key, main_symmetric_key)

    # store cloud_channel_id, msg_id, file_path, file_name, file_size, checksum, time
    create_database()

    # create cloud channel to store files
    channel_id = await create_channel(client)
    config = {
        "api_id": api_id,
        "api_hash": api_hash,
        "cloud_channel_id": channel_id,
        "cloud_channels": {
            "main": channel_id,  # default cloud channel
        },
        "encrypted_symmetric_key": encrypted_main_symmetric_key.hex(),
        "pulled_directory": default_pulled_dir,
        "is_auto_fill_password": {"status": False, "value": None},
    }
    write_file(CONFIG_PATH, config, mode="w", serialize=True)

    await set_channel_photo(client, channel_id)
    print(f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RESET} Cloud channel created")
