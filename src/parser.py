import os
import sys
import time
import argparse
from getpass import getpass

from colorama import Fore, Style

from src.config import Config


def _parse_args():
    parser = argparse.ArgumentParser(add_help=False)

    # Required arguments
    parser.add_argument(
        "action",
        choices=["push", "pull"],
    )
    parser.add_argument("target_path")

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

    return parser.parse_args()


def load_config():
    if sys.argv[1] not in ("push", "pull"):
        print("Usage: tc push/pull")
        exit()

    args = _parse_args()

    if (
        args.max_size[-2:] not in ("KB", "MB", "GB")
        or not (args.max_size[:-2]).strip().isdigit()
    ):
        print("Only accept KB, MB, GB. Ex: 1KB, 1 MB, 1  GB")
        exit()

    target_path = os.path.abspath(args.target_path)
    if args.action == "push" and not os.path.exists(target_path):
        print(
            f"{Style.BRIGHT}{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Style.RESET_ALL}{Fore.RED} - Path not found"
        )
        exit()

    password = args.password if args.password else getpass()

    return Config(
        action=args.action,
        target_path=target_path,
        password=password,
        excluded_dirs=args.excluded_dirs,
        excluded_files=args.excluded_files,
        excluded_file_suffixes=args.excluded_file_suffixes,
        is_recursive=args.is_recursive,
        in_name=args.in_name,
        max_size=args.max_size,
    )
