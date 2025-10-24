import time
import json

from colorama import Style, Fore
from telethon import TelegramClient

from .. import aes, rsa
from ..loaders import load_symmetric_key
from ..utils import write_file
from ..constants import ENCRYPTED_PRIVATE_KEY_PATH
from ..tl import create_channel, set_channel_photo
from ..cloudmap.functions.config import get_config, update_config


def add_password_to_config(password):
    config = get_config()
    config["is_auto_fill_password"] = {"status": True, "value": password}

    update_config(config)


def remove_password_from_config():
    config = get_config()
    config["is_auto_fill_password"] = {"status": False, "value": None}

    update_config(config)


def change_password(old_password, new_password):
    result = load_symmetric_key(old_password)
    if not result["success"]:
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET} - {result['error']}{Style.RESET_ALL}"
        )
        return

    new_private_key, new_public_key = rsa.generate_keys()

    new_encrypted_main_symmetric_key = rsa.encrypt(
        new_public_key, result["symmetric_key"]
    )
    config = get_config()
    config["encrypted_symmetric_key"] = new_encrypted_main_symmetric_key.hex()
    update_config(config)

    salt_for_private_key = os.urandom(32)
    symmetric_key_for_private_key = aes.generate_key(new_password, salt_for_private_key)

    new_encrypted_private_key = aes.encrypt(
        symmetric_key_for_private_key, new_private_key
    )
    write_file(ENCRYPTED_PRIVATE_KEY_PATH, salt_for_private_key)
    write_file(ENCRYPTED_PRIVATE_KEY_PATH, new_encrypted_private_key, mode="ab")

    print(
        f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Password has been changed {Fore.RESET}"
    )


def change_new_default_pulled_directory(new_directory):
    absolute_path = os.path.abspath(new_directory)
    if not os.path.exists(absolute_path):
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET} - Directory path not found"
        )
        return
    if not os.path.isdir(absolute_path):
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET} - Not a directory"
        )
        return

    config = get_config()
    config["pulled_directory"] = absolute_path
    update_config(config)

    print(
        f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Default pulled directory has been changed {Fore.RESET}"
    )


def show_all_config_setting():
    config = get_config()
    for key in config:
        if isinstance(config[key], dict):
            print(
                f"+ {Fore.GREEN}{key}{Fore.RESET}: {json.dumps(config[key], indent=4)}"
            )
        else:
            print(f"+ {Fore.GREEN}{key}{Fore.RESET}: {config[key]}")


async def create_new_cloudchannel(client: TelegramClient):
    config = get_config()

    title = input("Title: ").strip()

    if title in config["cloud_channels"]:
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET} - Cloud channel already exists"
        )
        return

    description = input("Description: ")

    # confirm again just to make sure "you" like the channel name
    confirm = input("[*] confirm? y/n:")
    if confirm != "y":
        return

    channel_id = await create_channel(client, title, description)
    await set_channel_photo(client, channel_id, title + ".jpg")

    config["cloud_channels"][title] = channel_id
    update_config(config)

    print(
        f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RESET} New cloud channel created: {Fore.GREEN}{title}{Fore.RESET}"
    )


def switch_cloud_channel(cloud_channel_name):
    config = get_config()

    if cloud_channel_name not in config["cloud_channels"]:
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET} - Cloud not found"
        )
        return

    switched_cloud_channel_id = config["cloud_channels"][cloud_channel_name]
    config["cloud_channel_id"] = switched_cloud_channel_id
    update_config(config)

    print(
        f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RESET} Switched to {Fore.GREEN}{cloud_channel_name}{Fore.RESET}"
    )


def show_all_cloud_channels():
    config = get_config()

    current_channel_id = config["cloud_channel_id"]

    for channel_name in config["cloud_channels"]:
        channel_id = config["cloud_channels"][channel_name]
        if channel_id == current_channel_id:
            print(f"* {Fore.GREEN}{channel_name}{Fore.RESET}")
        else:
            print(f"  {channel_name}")
