# curses isn't included in windows python by default, to install it, run pip install windows-curses
# the python docs on curses are really useful https://docs.python.org/3/howto/curses.html would suggest

# TODO Refactor this code into a class system, as opposed to a set of functions.

import curses
import time
from typing import Literal, NoReturn
import json
import sys
import os
from fnmatch import fnmatch


class uio:
    def __init__(self):
        self.stdscr = curses.initscr()
        # uio_log is kept open, and only closed when program quits, this is so we can
        self.uio_log_path = "uio.log"
        self.uio_log = open(self.uio_log_path, "a")
        self.write_log("Info", "----- Program Launched -----")

        self.conf_file_path = None
        self.conf = None
        self.msgs = None

        error_codes = []
        conf_success = self.load_conf()
        if conf_success != 0:
            error_codes.append(conf_success)

        # msgs is a list of dicts [{"username": str-username, "message": str-message},...]
        # note when chat history sharing is implemented, msgs with username "system" shouldn't be shared
        # and "system" should not be allowed as a username
        try:
            with open(self.conf["chat_history_path"], "+a") as f:
                f.seek(0)
                contents = f.read()
                if contents == "":
                    f.write("[]\n")
                self.msgs = json.loads(contents)
        except Exception as e:
            self.write_log(
                "Error",
                f'Failed to open or create chat history file at {self.conf["chat_history_path"]}, attempting to proceed without. {type(e)} {e}',
            )
            self.msgs = [
                {
                    "username": "system",
                    "message": "Failed to load chat history. See uio.log for details",
                }
            ]
            self.write_chat_history_file()

        try:
            main(stdscr, msgs, error_codes)
        except KeyboardInterrupt:
            self.write_log(
                "Info",
                "Exiting normally after KeyboardInterrupt (usually occurs after pressing ctrl+c)",
            )
            exit_program(stdscr)
        except Exception as e:
            self.write_log(
                "FatalError",
                f"Exiting after an unexpected exception occurred. {type(e)} {e}",
            )
            exit_program(stdscr)

    def write_chat_history_file(self) -> None:
        try:
            with open(self.conf["chat_history_path"], "w") as chat_history_file:
                chat_history_file.write(json.dumps(self.msgs, indent=4))
        except Exception as e:
            self.write_log(
                "Error",
                f'Failed to write a message to {self.conf["chat_history_path"]}, {type(e)} {e}',
            )

    def __load_conf(self, conf_path: str | None = None) -> int:
        """Loads the file at the specified file path as a config, or attempts to find or create a .conf to load instead.

        Args:
            conf_path (str | None, optional): The path to a .conf file to load. When None or not given, automatically finds or creates a .conf

        Returns:
            int: for conf_path = None: 0 if created a conf, 1 if failed to load or create a conf, 2 if loaded a conf.
                for conf_path = str: 0 if no errors, 1 if failed to load conf.
        """
        # Forgive me for my sins, the control flow of this 100+ line function is a nightmare of nested if statements.
        # TODO Refactor load_conf
        # Im sure we'll get to doing this eventually,
        # but for now, have fun trying to hold in your head all the conditions of last 3 if statements.
        # God I hope there aren't any errors here, for your sake and mine.

        self.conf_file_path = None
        config_success = -1
        if conf_path == None:
            configs: list[str] = self.find_file("*.conf", ".")
            if len(configs) == 0:
                # no conf found, make one
                self.write_log(
                    "Info", f"No config file found, attempting to create user.conf"
                )
                try:
                    with open("user.conf", "w") as f:
                        self.conf = {
                            "username": "anonymous",
                            "chat_history_path": "LocalChatHistory.json",
                        }
                        f.write(json.dumps(self.conf, indent=4))
                        self.conf_file_path = "user.conf"
                        self.write_log("Info", "Successfully created user.conf")
                        config_success = 0
                except Exception as e:
                    # couldn't make one, proceed without
                    self.write_log(
                        "Error",
                        f"Failed to create config file user.conf, proceeding without a conf file. {type(e)} {e}",
                    )
                    self.conf = {
                        "username": "anonymous",
                        "chat_history_path": "LocalChatHistory.json",
                    }
                    config_success = 1
            else:
                # we found one or more conf, try to use them
                for config in configs:
                    self.write_log(
                        "Info",
                        f"found {len(configs)} conf file{"s" if len(configs) > 1 else ""}, trying {config}",
                    )
                    try:
                        with open(config, "r") as f:
                            f.seek(0)
                            contents = f.read()
                            self.conf = json.loads(contents)
                            if self.conf["username"] == "system":
                                raise RuntimeError(
                                    f"username in conf {config} is system, username cannot be system"
                                )
                            self.conf_file_path = config
                            config_success = 2
                            self.write_log(
                                "Info", f"Successfully loaded config {config}"
                            )
                            break
                    except Exception as e:
                        # couldn't use that conf,
                        self.write_log(
                            "Warning",
                            f"Failed to load config file at {config} {type(e)} {e}",
                        )
                if config_success != 2:
                    self.write_log(
                        "Error",
                        "Unable to load any of the found config files. Proceeding without a conf file.",
                    )
                    self.conf = {
                        "username": "anonymous",
                        "chat_history_path": "LocalChatHistory.json",
                    }
                    config_success = 1
        else:
            self.write_log(
                "Info",
                f"Attempting to load config file {conf_path}",
            )
            try:
                with open(conf_path, "r") as f:
                    f.seek(0)
                    contents = f.read()
                    self.conf = json.loads(contents)
                    self.conf_file_path = conf_path
                    config_success = 0
            except Exception as e:
                # couldn't use that conf,
                self.write_log(
                    "Error",
                    f"Failed to load config file at {config} {type(e)} {e}",
                )
                config_success = 1

        return config_success

    def write_log(
        self, err_level: str | Literal["FatalError", "Error", "Warning", "Info"], msg
    ) -> int:
        """Writes something to uio.log in the format 'YYYY:MM:DD hh:mm:ss, {err_level}: "{msg}"\\n' and returns success.
        If global uio_log already exists, uses that, otherwise, opens uio.log and uses that.
        msg text can contain apostrophes (') but should not contain quotation marks (")

        Args:
            err_level (Literal["FatalError", "Error", "Warning", "Info"]): The log severity, should be 1 of the 4 offered options, can be an any str.
            msg (str): The message to write.

        Returns:
            int: Errors, 0 if writing succeeded with no errors, 1 if it failed
        """
        log_msg = f'{time.strftime("%Y/%m/%d %H:%M:%S")}, {err_level}: "{msg}"\n'
        try:
            self.uio_log.write(log_msg)
            return 0
        except:
            try:
                self.uio_log = open(self.uio_log_path, "a")
                self.uio_log.write(log_msg)
                return 0
            except:
                return 1


if __name__ == "__main__":
    user_io = uio()
