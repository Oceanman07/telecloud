import os

from .utils import convert_bytes_to_int


class Config:
    def __init__(
        self,
        api_id,
        api_hash,
        action,
        target_path,
        password,
        new_password,
        is_recursive,
        excluded_dirs,
        excluded_files,
        excluded_file_suffixes,
        in_name,
        max_size,
        is_auto_fill_password,
    ):
        self.__api_id = api_id
        self.__api_hash = api_hash
        self.__action = action
        self.__target_path = target_path
        self.__password = password
        self.__new_password = new_password
        self.__is_recursive = is_recursive
        self.__excluded_dirs = excluded_dirs
        self.__excluded_files = excluded_files
        self.__excluded_file_suffixes = excluded_file_suffixes
        self.__in_name = in_name
        self.__max_size = max_size
        self.__is_auto_fill_password = is_auto_fill_password

    @property
    def api_id(self):
        return self.__api_id

    @property
    def api_hash(self):
        return self.__api_hash

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
    def new_password(self):
        return self.__new_password

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
        return lambda _: False

    @property
    def max_size(self):
        return convert_bytes_to_int(self.__max_size)

    @property
    def is_auto_fill_password(self):
        return self.__is_auto_fill_password
