import os
import sys
import json
import time
import argparse
from getpass import getpass

from colorama import Fore

from .config import Config
from .constants import CONFIG_PATH
from .cloudmap.functions import (
    get_api_id,
    get_api_hash,
    get_default_pulled_directory,
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
        "--autofill-password",
        dest="is_auto_fill_password",
        choices=["true", "false"],
        help="Set automatic filling the password",
    )

    parser.add_argument(
        "--change-password",
        dest="new_password",
        help="Change new password for TeleCloud",
    )

    parser.add_argument(
        "--change-pulled-dir",
        dest="new_default_pulled_dir",
        help="Change new default pulled directory",
    )

    parser.add_argument(
        "--new-cloudchannel",
        dest="new_cloudchannel",
        action="store_true",
        help="Create a new cloud channel to store files",
    )

    parser.add_argument(
        "--switch-cloudchannel",
        dest="switched_cloudchannel",
        help="Switch to another cloud channel",
    )

    parser.add_argument(
        "--all-cloudchannels",
        dest="show_all_cloudchannels",
        action="store_true",
        help="Show all cloud channels",
    )

    return parser.parse_args()


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(
            f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Setup your TeleCloud{Fore.RESET}"
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
                f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET}   Pushing requires an existing path"
            )
            exit()

        absolute_path = os.path.abspath(args.target_path)
        # pushing requires an existing file/dir path
        if not os.path.exists(absolute_path):
            print(
                f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET} - Path not found"
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
    # in the setup step -> the password will be asked
    # and list command does not need password
    if not os.path.exists(CONFIG_PATH) or args.action == "list":
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

    return Config(
        api_id=api_id,
        api_hash=api_hash,
        action=args.action,
        target_path=target_path,
        password=password,
        new_password=args.new_password,
        new_default_pulled_dir=args.new_default_pulled_dir,
        new_cloudchannel=args.new_cloudchannel,
        show_all_cloudchannels=args.show_all_cloudchannels,
        switched_cloudchannel=args.switched_cloudchannel,
        excluded_dirs=args.excluded_dirs,
        excluded_files=args.excluded_files,
        excluded_file_suffixes=args.excluded_file_suffixes,
        is_recursive=args.is_recursive,
        in_name=args.in_name,
        max_size=args.max_size,
        is_auto_fill_password=args.is_auto_fill_password,
    )
