import os
import sys
import json
import time
import argparse
from getpass import getpass

from colorama import Fore, Style

from .config import Config
from .constants import STORED_CLOUDMAP_PATHS, CONFIG_PATH
from .cloudmapmanager import get_api_id, get_api_hash, get_salt_from_cloudmap


def _parse_args():
    parser = argparse.ArgumentParser(add_help=False)

    # Required arguments
    parser.add_argument(
        "action",
        choices=["push", "pull", "list", "config"],
    )
    parser.add_argument("target_path", nargs="?")

    # Optional arguments
    parser.add_argument(
        "-p", "--password", dest="password"
    )  # if password is not provided, the program will ask

    parser.add_argument("-r", "--recursion", dest="is_recursive", action="store_true")

    parser.add_argument(
        "-ed", "--excluded-dir", dest="excluded_dirs", action="append", default=[]
    )

    parser.add_argument(
        "-ef", "--excluded-file", dest="excluded_files", action="append", default=[]
    )

    parser.add_argument(
        "-es",
        "--excluded-file-suffix",
        dest="excluded_file_suffixes",
        action="append",
        default=[],
    )

    parser.add_argument("-n", "--in-name", dest="in_name")

    parser.add_argument("-ms", "--max-size", dest="max_size", default="2GB")

    parser.add_argument(
        "--auto-fill-password",
        dest="is_auto_fill_password",
        choices=["true", "false"],
    )

    return parser.parse_args()


def load_config():
    os.makedirs(STORED_CLOUDMAP_PATHS, exist_ok=True)

    if sys.argv[1] not in ("push", "pull", "list", "config"):
        print("Usage: tc push/pull [target_path]")
        exit()

    if not os.path.exists(CONFIG_PATH):
        api_id = int(input("Please enter your app api_id: "))
        api_hash = input("Please enter your app api_hash: ")
    else:
        api_id = get_api_id()
        api_hash = get_api_hash()

    args = _parse_args()

    if args.action in ("push", "pull") and not args.target_path:
        print("Usage: tc push/pull [target_path]")
        exit()

    if (
        args.max_size[-2:] not in ("KB", "MB", "GB")
        or not (args.max_size[:-2]).strip().isdigit()
    ):
        print("Only accept KB, MB, GB. Ex: 1KB, 1 MB, 1  GB")
        exit()

    target_path = (
        os.path.abspath(args.target_path)
        if args.action != "list" and args.action != "config"
        else "None"
    )
    if args.action == "push" and not os.path.exists(target_path):
        print(
            f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}{Fore.RED} - Path not found"
        )
        exit()

    if not os.path.exists(CONFIG_PATH) or args.action == "list":
        # CONFIG_PATH does not exist means the program have not setup yet
        # in the setup step -> the salt will be generated and the password will be asked
        salt = b"No need yet"
        password = "No need yet"
    else:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)

        if args.password:
            password = args.password
        elif config["is_auto_fill_password"]["status"]:
            password = config["is_auto_fill_password"]["value"]
        elif args.is_auto_fill_password == "false":
            password = "No need yet"
        else:
            password = getpass()

        salt = get_salt_from_cloudmap()

    return Config(
        api_id=api_id,
        api_hash=api_hash,
        salt=salt,
        action=args.action,
        target_path=target_path,
        password=password,
        excluded_dirs=args.excluded_dirs,
        excluded_files=args.excluded_files,
        excluded_file_suffixes=args.excluded_file_suffixes,
        is_recursive=args.is_recursive,
        in_name=args.in_name,
        max_size=args.max_size,
        is_auto_fill_password=args.is_auto_fill_password,
    )
