from colorama import Fore

from ._data_preparer import DataFilter
from ..config_manager.config import Config
from ..cloudmap import get_cloudmap
from ..utils import convert_bytes


def list_pushed_files(config: Config):
    cloudmap = get_cloudmap()
    filter = DataFilter(
        excluded_dirs=None,
        excluded_files=config.excluded_files,
        excluded_file_suffixes=config.excluded_file_suffixes,
        max_size=config.max_size,
        in_name=config.in_name,
    )

    count = 0
    for pushed_file in cloudmap:
        file_name = pushed_file["file_name"]
        file_size = pushed_file["file_size"]

        if not filter.is_valid_file(file_name):
            continue
        if not filter.is_valid_file_suffix(file_name):
            continue
        if not filter.is_valid_size(file_size):
            continue
        if not filter.is_match_in_name(file_name):
            continue

        count += 1
        print(
            f"[{count}] {file_name}  - {Fore.GREEN}{convert_bytes(file_size)}{Fore.RESET}"
        )
