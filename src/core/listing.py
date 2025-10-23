from colorama import Fore

from ..config import Config
from ..cloudmap.functions.cloudmap import get_cloudmap
from ..utils import convert_bytes


def list_pushed_files(config: Config):
    cloudmap = get_cloudmap()

    filter_name_func = config.filter_name_func

    count = 0
    for pushed_file in cloudmap:
        file_name = pushed_file["file_name"]
        file_size = pushed_file["file_size"]

        if file_name in config.excluded_files:
            continue
        if any(file_name.endswith(suffix) for suffix in config.excluded_file_suffixes):
            continue
        if not filter_name_func(file_name):
            continue

        count += 1
        print(
            f"[{count}] {file_name}  - {Fore.GREEN}{convert_bytes(file_size)}{Fore.RESET}"
        )
