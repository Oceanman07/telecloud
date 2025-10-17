import os
import json
import time

from colorama import Style, Fore

from .. import aes, rsa
from ..protector import load_symmetric_key
from ..config import Config
from ..utils import read_file, write_file
from ..constants import CONFIG_PATH, ENCRYPTED_PRIVATE_KEY_PATH


def _add_password_to_config(password):
    with open(CONFIG_PATH, "r") as f:
        file_content = json.load(f)
        file_content["is_auto_fill_password"] = {"status": True, "value": password}

    with open(CONFIG_PATH, "w") as f:
        json.dump(file_content, f)


def _remove_password_from_config():
    with open(CONFIG_PATH, "r") as f:
        file_content = json.load(f)
        file_content["is_auto_fill_password"] = {"status": False, "value": None}

    with open(CONFIG_PATH, "w") as f:
        json.dump(file_content, f)


async def _change_password(old_password, new_password):
    result = await load_symmetric_key(old_password)
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


async def set_config(config: Config):
    # when setting config -> blocking io does not matter at all
    if config.is_auto_fill_password == "true":
        _add_password_to_config(config.password)
    elif config.is_auto_fill_password == "false":
        _remove_password_from_config()
    elif config.new_password:
        await _change_password(config.password, config.new_password)
