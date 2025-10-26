import os
import json
import time
import argparse
from getpass import getpass

from colorama import Fore

from .config import Config
from ..constants import CONFIG_PATH
from ..cloudmap.functions.config import (
    get_config,
    get_api_id,
    get_api_hash,
    get_default_pulled_directory,
)


def _parse_args():
    parser = argparse.ArgumentParser(
        usage="tc [options] [command] [target_path only for push/pull]",
        epilog=(
            "for more convienent you might need to run this command:\n"
            "   `tc -p your_password config --autofill-password true`\n"
            "to unset, run:\n"
            "   `tc config --autofill-password false"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Main commands
    subparsers = parser.add_subparsers(
        title="Main commands",
        dest="command",
        required=True,
        metavar="using `tc [command] -h` for more\n",
    )

    # pushing command
    push = subparsers.add_parser(
        "push",
        usage="tc [options] push [target_path]",
        description=(
            "if you want to push a whole directory where it contains big size files, "
            "you should push that big MB or GB file as a single file cause it will be faster\n\n"
            "example:\n"
            "   tc -ms 20MB push example_dir/\n"
            "  then:\n"
            "   tc push example_dir/really_big_file.mp4"
        ),
        help="upload files to cloud channel",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    push.add_argument("target_path", help="a file or directory")
    push.add_argument(
        "-r",
        "--recursion",
        dest="is_recursive",
        action="store_true",
        help="process recursively subdirectories",
    )

    # pulling command
    pull = subparsers.add_parser(
        "pull",
        usage="tc [options] pull [target_path]",
        description=(
            "if you do not provide a pushed file name or a stored directory, "
            "files will be downloaded and stored in the default pulled directory\n"
            "also, if you want to pull every pushed files which may contain big size files, "
            "you should pull that big MB or GB file as a single file cause it will be faster\n\n"
            "example:\n"
            "   tc -ms 20MB pull\n"
            "  then:\n"
            "   tc pull really_big_file.mp4  # note that this file will be stored in the current directory"
        ),
        help="download files from cloud channel",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    pull.add_argument(
        "target_path", nargs="?", help="a pushed file name or a stored directory"
    )

    # setting config command
    config = subparsers.add_parser(
        "config",
        usage="tc config [options]",
        description="if options not provided, all config settings will be listed",
        help="show or set config options",
    )
    config.add_argument(
        "--autofill-password",
        dest="is_auto_fill_password",
        choices=["true", "false"],
        help="set automatic filling the password",
    )
    config.add_argument(
        "--change-password",
        dest="new_password",
        help="change a new password for using telecloud",
    )
    config.add_argument(
        "--change-pulled-dir",
        dest="new_default_pulled_dir",
        help="change a new default pulled directory",
    )

    # setting channel command
    channel = subparsers.add_parser(
        "channel",
        usage="tc channel [options]",
        description="if options not provided, all cloud channels will be listed",
        help="list, create, switch or delete cloud channels",
    )
    channel.add_argument(
        "--new",
        dest="new_cloudchannel",
        action="store_true",
        help="create a new cloud channel",
    )
    channel.add_argument(
        "-s",
        "--switch",
        dest="switched_cloudchannel",
        help="switch to another cloud channel",
    )
    channel.add_argument(
        "-d", "--delete", dest="deleted_cloudchannel", help="delete a cloud channel"
    )

    # listing pushed files command
    listing = subparsers.add_parser(
        "list",
        usage="tc [options] list",
        description=('example:\n   tc -n "*png" list'),
        help="list pushed files",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # General options
    general = parser.add_argument_group(
        "General options",
        "These options can be used to do general works",
    )
    # if password is not provided, the program will ask
    general.add_argument(
        "-p",
        "--password",
        dest="password",
        help="password for generating key to encrypt/decrypt file (the program will ask if not provided)",
    )
    general.add_argument(
        "-n",
        "--in-name",
        dest="in_name",
        help=(
            'filter in wanted specific file name pattern\nexample:\n   -n "fuc*" or -n "*k" or -n "*you*"'
        ),
    )
    general.add_argument(
        "-ed",
        "--excluded-dir",
        dest="excluded_dirs",
        action="append",
        default=[],
        help=(
            "filter out unwanted directories\nexample:\n   -ed unwanted_dir -ed excluded_dir -ed .git"
        ),
    )
    general.add_argument(
        "-ef",
        "--excluded-file",
        dest="excluded_files",
        action="append",
        default=[],
        help=(
            "filter out unwanted files\nexample:\n   -ef text.txt -ef .gitignore -ef movie.mp4"
        ),
    )
    general.add_argument(
        "-es",
        "--excluded-file-suffix",
        dest="excluded_file_suffixes",
        action="append",
        default=[],
        help=(
            "filter out unwanted file suffixes\nexample:\n   -es mp4 -es mkv -es mp3"
        ),
    )
    general.add_argument(
        "-ms",
        "--max-size",
        dest="max_size",
        default="2GB",
        help="the maxinum allowed size of a file\nexample:\n   -ms 2KB or -ms 30MB or -ms 4GB",
    )

    return parser.parse_args()


def load_config():
    args = _parse_args()

    if args.command == "push":
        absolute_path = os.path.abspath(args.target_path)
        # pushing requires an existing file/dir path
        if not os.path.exists(absolute_path):
            print(
                f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.RED} Failed{Fore.RESET} - Path not found"
            )
            exit()

        target_path = {"is_file": os.path.isfile(absolute_path), "value": absolute_path}

    elif args.command == "pull":
        if not args.target_path:
            default_dir = get_default_pulled_directory()
            target_path = {"is_file": False, "value": default_dir}
            os.makedirs(default_dir, exist_ok=True)
        else:
            absolute_path = os.path.abspath(args.target_path)
            if os.path.isdir(absolute_path):
                target_path = {"is_file": False, "value": absolute_path}
            else:
                target_path = {"is_file": True, "value": absolute_path}

    else:
        # only pushing/pulling command uses target_path -> they do not touch it then target_path can be anything
        target_path = {}

    # check if the max_size arg is valid or not
    if (
        args.max_size[-2:].upper() not in ("KB", "MB", "GB")
        or not (args.max_size[:-2]).strip().isdigit()
    ):
        print("Only accept KB, MB, GB. Ex: 1KB, 1 MB, 1  GB")
        exit()

    # CONFIG_PATH does not exist means the program have not setup yet
    # in the setup step -> the password will be asked
    # and some commands may require the password
    password = "No need yet"
    if not os.path.exists(CONFIG_PATH) or args.command == "list":
        pass

    elif args.command == "config":
        if args.new_password or args.is_auto_fill_password == "true":
            password = _get_password(args)

    elif args.command == "channel":
        if args.new_cloudchannel or args.deleted_cloudchannel:
            password = _get_password(args)

    else:
        password = _get_password(args)

    return Config(
        api_id=get_api_id(),
        api_hash=get_api_hash(),
        command=args.command,
        target_path=target_path,
        password=password,
        new_default_pulled_dir=_set_none_if_uncalled_attrib(
            args, "new_default_pulled_dir"
        ),
        switched_cloudchannel=_set_none_if_uncalled_attrib(
            args, "switched_cloudchannel"
        ),
        excluded_file_suffixes=_set_none_if_uncalled_attrib(
            args, "excluded_file_suffixes"
        ),
        is_auto_fill_password=_set_none_if_uncalled_attrib(
            args, "is_auto_fill_password"
        ),
        in_name=_set_none_if_uncalled_attrib(args, "in_name"),
        max_size=_set_none_if_uncalled_attrib(args, "max_size"),
        is_recursive=_set_none_if_uncalled_attrib(args, "is_recursive"),
        new_password=_set_none_if_uncalled_attrib(args, "new_password"),
        excluded_dirs=_set_none_if_uncalled_attrib(args, "excluded_dirs"),
        excluded_files=_set_none_if_uncalled_attrib(args, "excluded_files"),
        new_cloudchannel=_set_none_if_uncalled_attrib(args, "new_cloudchannel"),
        deleted_cloudchannel=_set_none_if_uncalled_attrib(args, "deleted_cloudchannel"),
    )


def _get_password(args):
    config = get_config()

    if args.password:
        return args.password
    elif config["is_auto_fill_password"]["status"]:
        return config["is_auto_fill_password"]["value"]
    return getpass()


def _set_none_if_uncalled_attrib(args, attrib_name):
    if attrib_name == "new_password":
        return args.new_password if attrib_name in args else None
    elif attrib_name == "new_default_pulled_dir":
        return args.new_default_pulled_dir if attrib_name in args else None
    elif attrib_name == "new_cloudchannel":
        return args.new_cloudchannel if attrib_name in args else None
    elif attrib_name == "switched_cloudchannel":
        return args.switched_cloudchannel if attrib_name in args else None
    elif attrib_name == "deleted_cloudchannel":
        return args.deleted_cloudchannel if attrib_name in args else None
    elif attrib_name == "excluded_dirs":
        return args.excluded_dirs if attrib_name in args else None
    elif attrib_name == "excluded_files":
        return args.excluded_files if attrib_name in args else None
    elif attrib_name == "excluded_file_suffixes":
        return args.excluded_file_suffixes if attrib_name in args else None
    elif attrib_name == "is_recursive":
        return args.is_recursive if attrib_name in args else None
    elif attrib_name == "in_name":
        return args.in_name if attrib_name in args else None
    elif attrib_name == "max_size":
        return args.max_size if attrib_name in args else None
    elif attrib_name == "is_auto_fill_password":
        return args.is_auto_fill_password if attrib_name in args else None
