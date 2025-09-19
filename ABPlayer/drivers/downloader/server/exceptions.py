class DownloaderError(Exception):
    code: int
    message: str

    def __init__(self):
        super().__init__(f"[{self.code}] {self.message}")


class IncorrectMessage(DownloaderError):
    code = 1
    message = "Incorrect message"


class UnknownCommand(DownloaderError):
    code = 2
    message = "Unknown command"


class ParamNotPassed(DownloaderError):
    code = 3
    message = "{param_name} not passed"

    def __init__(self, param_name: str):
        self.param_name = param_name
        self.message = self.message.format(param_name=param_name)
        super().__init__()
