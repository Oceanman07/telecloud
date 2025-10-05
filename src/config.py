import os

from .utils import convert_bytes_to_int


class Config:
    def __init__(
        self,
        action,
        target_path,
        password,
        is_recursive,
        excluded_dirs,
        excluded_files,
        excluded_file_suffixes,
        in_name,
        max_size,
    ):
        self.__action = action
        self.__target_path = target_path
        self.__password = password
        self.__is_recursive = is_recursive
        self.__excluded_dirs = excluded_dirs
        self.__excluded_files = excluded_files
        self.__excluded_file_suffixes = excluded_file_suffixes
        self.__in_name = in_name
        self.__max_size = max_size

    @property
    def action(self):
        return self.__action

    @property
    def target_path(self):
        return self.__target_path

    @property
    def password(self):
        return self.__password

    @property
    def is_recursive(self):
        return self.__is_recursive

    @property
    def excluded_dirs(self):
        return [os.path.basename(excluded_dir) for excluded_dir in self.__excluded_dirs]

    @property
    def excluded_files(self):
        return [
            os.path.basename(excluded_file) for excluded_file in self.__excluded_files
        ]

    @property
    def excluded_file_suffixes(self):
        return self.__excluded_file_suffixes

    @property
    def filter_name_func(self):
        if self.__in_name is None:
            return lambda _: True
        if self.__in_name.startswith("*") and self.__in_name.endswith("*"):
            return lambda file_name: self.__in_name[1:-1] in file_name
        if self.__in_name.startswith("*"):
            return lambda file_name: file_name.endswith(self.__in_name[1:])
        if self.__in_name.endswith("*"):
            return lambda file_name: file_name.startswith(self.__in_name[:-1])

    @property
    def max_size(self):
        return convert_bytes_to_int(self.__max_size)
