import os
import sys
import json
import time
import argparse
from getpass import getpass

from colorama import Fore, Style

from .config import Config
from .constants import CONFIG_PATH
from .cloudmapmanager import (
    get_api_id,
    get_api_hash,
    get_default_pulled_directory,
    get_salt_from_cloudmap,
)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Quick usage: tc push/pull [Optional args] [target_path]",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Required arguments

    parser.add_argument(
        "action",
        choices=["push", "pull", "config", "list"],
        help=(
            "push     upload files to cloud\n"
            "pull     download pushed files from cloud\n"
            "config   configure options\n"
            "list     show pushed files"
        ),
    )
    parser.add_argument(
        "target_path",
        nargs="?",  # since it only requires for pushing and pulling
        help="The file/dir path for pushing (an existing path) and pulling (a pushed file name or stored directory)",
    )

    # Optional arguments

    # if password is not provided, the program will ask
    parser.add_argument(
        "-p",
        "--password",
        dest="password",
        help="Password for generating key to encrypt/decrypt file",
    )

    parser.add_argument(
        "-r",
        "--recursion",
        dest="is_recursive",
        action="store_true",
        help="Process recursively subdirectories (for pushing)",
    )

    parser.add_argument(
        "-ed",
        "--excluded-dir",
        dest="excluded_dirs",
        action="append",
        default=[],
        help="Filter out unwanted directories",
    )

    parser.add_argument(
        "-ef",
        "--excluded-file",
        dest="excluded_files",
        action="append",
        default=[],
        help="Filter out unwanted files",
    )

    parser.add_argument(
        "-es",
        "--excluded-file-suffix",
        dest="excluded_file_suffixes",
        action="append",
        default=[],
        help="Filter out unwanted file suffixes",
    )

    parser.add_argument(
        "-n",
        "--in-name",
        dest="in_name",
        help="Filter in wanted specific file name pattern",
    )

    parser.add_argument(
        "-ms",
        "--max-size",
        dest="max_size",
        default="2GB",
        help="The maxinum allowed size of a file when pushing/pulling",
    )

    parser.add_argument(
        "--auto-fill-password",
        dest="is_auto_fill_password",
        choices=["true", "false"],
        help="Set automatic filling the password",
    )

    return parser.parse_args()


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(
            f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Setup your TeleCloud{Style.RESET_ALL}"
        )
        api_id = int(input("Please enter your app api_id: "))
        api_hash = input("Please enter your app api_hash: ")
        print(
            "[*] Your phone number must be (telephone country code)+(your phone number)\n"
            "For example: 840123456789 (84 is a coutry code and the rest is your phone)"
        )
    else:
        api_id = get_api_id()
        api_hash = get_api_hash()

    args = _parse_args()

    if sys.argv[1] not in ("push", "pull", "config", "list"):
        print("usage: tc push/pull [Optional args] [target_path]")
        exit()

    if args.action == "push":
        if not args.target_path:
            print(
                f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}{Fore.RED} - Pushing requires an existing path{Style.RESET_ALL}"
            )
            exit()

        absolute_path = os.path.abspath(args.target_path)
        # pushing requires an existing file/dir path
        if not os.path.exists(absolute_path):
            print(
                f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}{Fore.RED} - Path not found{Style.RESET_ALL}"
            )
            exit()

        target_path = {"is_file": os.path.isfile(absolute_path), "value": absolute_path}

    elif args.action == "pull":
        if not args.target_path:
            target_path = {"is_file": False, "value": get_default_pulled_directory()}
            os.makedirs(get_default_pulled_directory(), exist_ok=True)
        else:
            absolute_directory_path = os.path.abspath(args.target_path)
            if os.path.isdir(absolute_directory_path):
                target_path = {"is_file": False, "value": absolute_directory_path}
            else:
                target_path = {"is_file": True, "value": absolute_directory_path}

    else:
        # only pushing/and pulling command use target_path -> they do not touch it then target_path can be anything
        target_path = {}

    # check if the max_size arg is valid or not
    if (
        args.max_size[-2:] not in ("KB", "MB", "GB")
        or not (args.max_size[:-2]).strip().isdigit()
    ):
        print("Only accept KB, MB, GB. Ex: 1KB, 1 MB, 1  GB")
        exit()

    # CONFIG_PATH does not exist means the program have not setup yet
    # in the setup step -> the salt will be generated and the password will be asked
    # and list command does not need password
    if not os.path.exists(CONFIG_PATH) or args.action == "list":
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
