import os
import time

from colorama import Style, Fore
from telethon import TelegramClient

from .. import aes, rsa
from ..protector import load_symmetric_key
from ..config import Config
from ..utils import read_file, write_file
from ..constants import CONFIG_PATH, ENCRYPTED_PRIVATE_KEY_PATH
from ..cloudmap.setup import create_channel, set_channel_photo


def _add_password_to_config(password):
    config = read_file(CONFIG_PATH, mode="r", deserialize=True)
    config["is_auto_fill_password"] = {"status": True, "value": password}

    write_file(CONFIG_PATH, config, mode="w", serialize=True)


def _remove_password_from_config():
    config = read_file(CONFIG_PATH, mode="r", deserialize=True)
    config["is_auto_fill_password"] = {"status": False, "value": None}

    write_file(CONFIG_PATH, config, mode="w", serialize=True)


def _change_password(old_password, new_password):
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
    config = read_file(CONFIG_PATH, mode="r", deserialize=True)
    config["encrypted_symmetric_key"] = new_encrypted_main_symmetric_key.hex()
    write_file(CONFIG_PATH, config, mode="w", serialize=True)

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


def _change_new_default_pulled_directory(new_directory):
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

    config = read_file(CONFIG_PATH, mode="r", deserialize=True)
    config["pulled_directory"] = absolute_path
    write_file(CONFIG_PATH, config, mode="w", serialize=True)

    print(
        f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Default pulled directory has been changed {Fore.RESET}"
    )


async def _create_new_cloudchannel(client: TelegramClient):
    config = read_file(CONFIG_PATH, mode="r", deserialize=True)

    title = input("Title: ").strip()

    if title in config["cloud_channels"]:
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET} - Cloud already exists"
        )
        return

    description = input("Description: ")

    channel_id = await create_channel(client, title, description)
    await set_channel_photo(client, channel_id, title + ".png")

    config["cloud_channels"][title] = channel_id
    write_file(CONFIG_PATH, config, mode="w", serialize=True)

    print(
        f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RESET} New cloud channel created: {Fore.GREEN}{title}{Fore.RESET}"
    )


def _switch_cloud_channel(cloud_channel_name):
    config = read_file(CONFIG_PATH, mode="r", deserialize=True)

    if cloud_channel_name not in config["cloud_channels"]:
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET} - Cloud not found"
        )
        return

    switched_cloud_channel_id = config["cloud_channels"][cloud_channel_name]
    config["cloud_channel_id"] = switched_cloud_channel_id

    write_file(CONFIG_PATH, config, mode="w", serialize=True)

    print(
        f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RESET} Switched to {Fore.GREEN}{cloud_channel_name}{Fore.RESET}"
    )


def _show_all_cloud_channels():
    config = read_file(CONFIG_PATH, mode="r", deserialize=True)

    current_channel_id = config["cloud_channel_id"]

    for channel_name in config["cloud_channels"]:
        channel_id = config["cloud_channels"][channel_name]
        if channel_id == current_channel_id:
            print(f"*{Fore.GREEN}{channel_name}{Fore.RESET}")
        else:
            print(f" {channel_name}")


async def set_config(config: Config, client=None):
    if config.is_auto_fill_password == "true":
        _add_password_to_config(config.password)
    elif config.is_auto_fill_password == "false":
        _remove_password_from_config()
    elif config.new_password:
        _change_password(config.password, config.new_password)
    elif config.new_default_pulled_dir:
        _change_new_default_pulled_directory(config.new_default_pulled_dir)
    elif config.new_cloudchannel:
        await _create_new_cloudchannel(client)
    elif config.switched_cloudchannel:
        _switch_cloud_channel(config.switched_cloudchannel)
    elif config.show_all_cloudchannels:
        _show_all_cloud_channels()
