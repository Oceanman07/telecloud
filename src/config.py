from .utils import convert_bytes_to_int


class Config:
    def __init__(
        self,
        action,
        password,
        file,
        directory,
        is_recursive,
        excluded_dirs,
        excluded_files,
        excluded_file_suffixes,
        max_size,
    ):
        self.__action = action
        self.__password = password
        self.__file = file
        self.__directory = directory
        self.__is_recursive = is_recursive
        self.__excluded_dirs = excluded_dirs
        self.__excluded_files = excluded_files
        self.__excluded_file_suffixes = excluded_file_suffixes
        self.__max_size = max_size

    @property
    def action(self):
        return self.__action

    @property
    def password(self):
        return self.__password

    @property
    def file(self):
        return self.__file

    @property
    def directory(self):
        return self.__directory

    @property
    def is_recursive(self):
        return self.__is_recursive

    @property
    def excluded_dirs(self):
        return self.__excluded_dirs

    @property
    def excluded_files(self):
        return self.__excluded_files

    @property
    def excluded_file_suffixes(self):
        return self.__excluded_file_suffixes

    @property
    def max_size(self):
        return convert_bytes_to_int(self.__max_size)
