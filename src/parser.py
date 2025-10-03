import sys
import argparse

from src.config import Config


def _parse_args():
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument(
        "action",
        choices=["push", "pull"],
    )

    parser.add_argument(
        "-d",
        "--dir",
        dest="directory",
    )

    parser.add_argument("-f", "--file", dest="file")

    parser.add_argument("-p", "--password", dest="password")

    return parser.parse_args()


def load_config():
    if sys.argv[1] not in ("push", "pull"):
        print("Usage: tc push/pull")
        exit()

    args = _parse_args()
    return Config(
        action=args.action,
        password=args.password,
        file=args.file,
        directory=args.directory,
    )
