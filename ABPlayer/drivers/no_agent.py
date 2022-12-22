from .base import Driver


class NoAgentDriver:
    def __enter__(self):
        Driver.get_browser()

    def __exit__(self, exc_type, exc_val, exc_tb):
        Driver.quit_driver()
