import os

from ..config import Config
from ..cloudmapmanager import get_cloudmap
from ..utils import convert_bytes


def list_pushed_files(config: Config):
    cloudmap = get_cloudmap()

    filter_name_func = config.filter_name_func

    count = 0
    for msg_id in cloudmap:
        file_name = os.path.basename(cloudmap[msg_id]["file_path"])
        file_size = cloudmap[msg_id]["file_size"]

        if file_name in config.excluded_files:
            continue
        if any(file_name.endswith(suffix) for suffix in config.excluded_file_suffixes):
            continue
        if not filter_name_func(file_name):
            continue

        count += 1
        print(f"[{count}] {file_name}  - {convert_bytes(file_size)}")
