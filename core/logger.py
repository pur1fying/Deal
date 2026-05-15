from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Union

try:
    from rich.console import Console
    from rich.markup import escape
except ModuleNotFoundError:
    Console = None

    def escape(message: str) -> str:
        return message


console = Console() if Console is not None else None


class Logger:
    """
    Logger class for logging.
    """

    def __init__(self, logger_signal=None):
        """
        :param logger_signal: Logger signal broadcasts log level and log message
        """
        self.logs = ""
        self.logger_signal = logger_signal
        self.log_file_path: Path | None = None
        if not self.logger_signal:
            try:
                from rich.traceback import install

                install(show_locals=True)
            except ModuleNotFoundError:
                pass
        self.logger = logging.getLogger("Auto-ChatGPT_Logger")
        formatter = logging.Formatter("%(levelname)8s |%(asctime)20s | %(message)s ")
        handler1 = logging.StreamHandler(stream=sys.stdout)
        handler1.setFormatter(formatter)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            self.logger.addHandler(handler1)

    def set_log_file(self, path: Path | str, *, reset: bool = True) -> None:
        """
        Save future logs to a file in addition to console/signal output.
        """
        self.log_file_path = Path(path)
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        if reset:
            self.log_file_path.write_text("", encoding="utf-8")

    def clear_log_file(self) -> None:
        self.log_file_path = None

    def __out__(self, message: str, level: int = 1, raw_print=False) -> None:
        """
        Output log.
        :param message: log message
        :param level: log level(1: INFO, 2: WARNING, 3: ERROR, 4: CRITICAL)
        :return: None
        """
        if level < 1 or level > 4:
            raise ValueError("Invalid log level")

        if raw_print:
            self.logs += message
            self.__write_file__(message)
            if self.logger_signal:
                self.logger_signal.emit(level, message)
            return

        while len(logging.root.handlers) > 0:
            logging.root.handlers.pop()

        levels_str = ["INFO", "WARNING", "ERROR", "CRITICAL"]
        levels_color = ["#2d8cf0", "#ff9900", "#ed3f14", "#3e0480"]
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        plain_message = f"{levels_str[level - 1]} | {timestamp} | {message}"
        self.__write_file__(plain_message)
        if self.logger_signal is not None:
            self.logs += f"{plain_message}\n"
            self.logger_signal.emit(level, message)
        elif console is not None:
            console.print(
                f"[{levels_color[level - 1]}]"
                f"{levels_str[level - 1]} |"
                f" {timestamp} |"
                f" {escape(message)}[/]",
                soft_wrap=True,
            )
        else:
            print(plain_message)

    def __write_file__(self, message: str) -> None:
        if self.log_file_path is None:
            return
        with self.log_file_path.open("a", encoding="utf-8") as handle:
            handle.write(message)
            if not message.endswith("\n"):
                handle.write("\n")

    def info(self, message: str) -> None:
        """
        :param message: log message

        Output info log.
        """
        self.__out__(message, 1)

    def warning(self, message: str) -> None:
        """
        :param message: log message

        Output warn log.
        """
        self.__out__(message, 2)

    def error(self, message: Union[str, Exception]) -> None:
        """
        :param message: log message or Exception object

        Output error log.
        """
        if isinstance(message, BaseException):
            exc_message = str(message)
            formatted_message = f"{type(message).__name__}: {exc_message}" if exc_message else type(message).__name__
            self.__out__(formatted_message, 3)
            return

        self.__out__(message, 3)

    def critical(self, message: str) -> None:
        """
        :param message: log message

        Output critical log.
        """
        self.__out__(message, 4)

    def attr(self, msg: str) -> None:
        """
        Output attr log.
        """
        self.__out__(f"<<< {msg} >>>", 1)

    def line(self) -> None:
        """
        Output line.
        """
        self.__out__(
            '<div style="font-family: Consolas, monospace;color:#2d8cf0;">--------------'
            "-------------------------------------------------------------"
            "-------------------</div>",
            raw_print=True,
        )


logger = Logger(None)
