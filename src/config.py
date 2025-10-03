class Config:
    def __init__(self, action, password, file, directory):
        self.__action = action
        self.__password = password
        self.__file = file
        self.__directory = directory

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
