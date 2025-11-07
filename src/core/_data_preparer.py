import os
import time

from colorama import Fore

from ..utils import get_checksum
from ..constants import NAMING_FILE_MAX_LENGTH
from ..cloudmap import (
    get_cloudmap,
    get_pushed_file_paths,
    get_pushed_file_names,
    get_pushed_checksums,
)


class DataFilter:
    def __init__(
        self, excluded_dirs, excluded_files, excluded_file_suffixes, max_size, in_name
    ):
        self.__excluded_dirs = excluded_dirs
        self.__excluded_files = excluded_files
        self.__excluded_file_suffixes = excluded_file_suffixes
        self.__max_size = max_size
        self.__in_name = in_name

    def is_valid_directory(self, directory_path):
        return os.path.basename(directory_path) not in self.__excluded_dirs

    def is_valid_file(self, file_name):
        return file_name not in self.__excluded_files

    def is_valid_file_suffix(self, file_name):
        return all(
            not file_name.endswith(suffix) for suffix in self.__excluded_file_suffixes
        )

    def is_valid_size(self, file_size):
        return file_size <= self.__max_size

    def is_match_in_name(self, file_name):
        if self.__in_name is None:
            return True
        if self.__in_name.startswith("*") and self.__in_name.endswith("*"):
            return self.__in_name[1:-1] in file_name
        if self.__in_name.startswith("*"):
            return file_name.endswith(self.__in_name[1:])
        if self.__in_name.endswith("*"):
            return file_name.startswith(self.__in_name[:-1])
        return False


class PushedDataPreparer(DataFilter):
    def __init__(
        self,
        root_directory,
        excluded_dirs,
        excluded_files,
        excluded_file_suffixes,
        max_size,
        in_name,
        is_recursive,
        force,
    ):
        super().__init__(
            excluded_dirs,
            excluded_files,
            excluded_file_suffixes,
            max_size,
            in_name,
        )
        self.__root_directory = root_directory
        self.__is_recursive = is_recursive
        self.__force = force

    def prepare(self):
        pushed_file_paths = get_pushed_file_paths()
        checksums = get_pushed_checksums()

        file_paths = []
        for dir_path, _, file_names in os.walk(self.__root_directory):
            if not self.is_valid_directory(dir_path):
                continue

            for file_name in file_names:
                file_path = os.path.join(dir_path, file_name)

                if not self.is_valid_file(file_name):
                    continue
                if not self.is_valid_file_suffix(file_name):
                    continue
                if not self.is_valid_size(os.path.getsize(file_path)):
                    continue
                if not self.is_match_in_name(file_name):
                    continue

                if self.__force:
                    file_paths.append(file_path)
                    continue

                if file_path not in pushed_file_paths:
                    file_paths.append(file_path)
                    continue

                if get_checksum(file_path) not in checksums:
                    file_paths.append(file_path)
                    continue

                print(
                    f"{Fore.BLUE}{time.strftime('%H:%M:%S')}{Fore.GREEN} Remained{Fore.RESET}   {file_path}"
                )

            if not self.__is_recursive:
                break

        return file_paths


class PulledDataPreparer(DataFilter):
    def __init__(
        self,
        saved_directory,
        excluded_files,
        excluded_file_suffixes,
        max_size,
        in_name,
    ):
        super().__init__(
            None,
            excluded_files,
            excluded_file_suffixes,
            max_size,
            in_name,
        )
        self.__saved_directory = saved_directory

    def prepare(self):
        cloudmap = get_cloudmap()
        pushed_file_names = get_pushed_file_names()
        pulled_files = os.listdir(self.__saved_directory)

        prepared_data = []
        for pushed_file in cloudmap:
            msg_id = pushed_file["msg_id"]
            file_name = pushed_file["file_name"]
            file_size = pushed_file["file_size"]
            pushed_time = pushed_file["time"]

            if not self.is_valid_file(file_name):
                continue
            if not self.is_valid_file_suffix(file_name):
                continue
            if not self.is_valid_size(file_size):
                continue
            if not self.is_match_in_name(file_name):
                continue

            # If a file has multiple uploads, when downloading we need to make its name different with time
            # since it shares the same name
            if pushed_file_names.count(file_name) != 1:
                differentor = "." + str(msg_id) + "." + pushed_time
                base, ext = os.path.splitext(file_name)
                new_file_name = base + differentor + ext

                if len(new_file_name) > NAMING_FILE_MAX_LENGTH:
                    # prevent filename reaches the limit (255 chars)
                    file_name = (
                        base[: -(len(differentor) + len(ext))] + differentor + ext
                    )
                else:
                    file_name = new_file_name

            # Check if the file is already pulled at the end
            # since we need the name with msg_id + time of multiple pushed file
            if file_name in pulled_files:
                continue

            saved_path = os.path.join(self.__saved_directory, file_name)
            prepared_data.append(
                {"msg_id": msg_id, "file_size": file_size, "saved_path": saved_path}
            )

        return prepared_data
