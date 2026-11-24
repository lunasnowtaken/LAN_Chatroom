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
        self.in_buf = ""

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
                self.write_log("Info", f"{contents}")
                if contents == "":
                    f.write("[]\n")
                    f.seek(0)
                    contents = f.read()
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
            self.main(error_codes)
        except KeyboardInterrupt:
            self.write_log(
                "Info",
                "Exiting normally after KeyboardInterrupt (usually occurs after pressing ctrl+c)",
            )
            self.exit()
        except Exception as e:
            self.write_log(
                "FatalError",
                f"Exiting after an unexpected exception occurred. {type(e)} {e}",
            )
            self.exit()

    def parse_input_buffer(self) -> None:
        if self.in_buf.lower() == "/exit":
            self.write_log("Info", "Exiting normally after /exit command")
            self.exit()
        elif self.in_buf.lower() == "/clear":
            try:
                chat_history_file = open(self.conf["chat_history_path"], "r")
                chat_history_file.seek(0)
                contents = chat_history_file.read()
                chat_history_file.close()

                # im unsure how the history file could be empty while msgs is not empty, but just in case
                if contents == "" and self.msgs == []:
                    self.write_log(
                        "Info",
                        f'No chat history to clear at {self.conf["chat_history_path"]}',
                    )
                else:
                    with open(self.conf["chat_history_path"], "w"):
                        self.msgs.clear()
                        self.write_log(
                            "Info",
                            f'Cleared chat history at {self.conf["chat_history_path"]}',
                        )
                        # Opening in write mode truncates the file first, so nothing else to do
            except Exception as e:
                self.write_log(
                    "Error",
                    f'Failed to clear chat history at {self.conf["chat_history_path"]} {type(e)} {e}',
                )
        elif self.in_buf[0:9].lower() == "/username":
            # takes as argument a new username for the user, if given no username, tells users current username

            # remove the "/username" part
            self.in_buf = self.in_buf[9:]
            # remove any whitespace
            self.in_buf = self.in_buf.replace(" ", "")
            if self.in_buf == "":
                # no new username given, echo current username
                self.write_log("Info", "/username called, echoing current username.")
                self.add_message(
                    "system",
                    f"Your username is: {self.conf["username"]}\\n To change, use /username <new_username>",
                )
            elif self.in_buf == "system":
                self.write_log(
                    "Info", "/username called with username system, no changes made."
                )
                self.add_message(
                    "system",
                    'Your username cannot be "system"',
                )
            else:
                self.write_log(
                    "Info",
                    f"/username called with valid username {self.in_buf}, changing username.",
                )
                self.conf["username"] = self.in_buf
                self.add_message(
                    "system",
                    f"Changed username to {self.in_buf}",
                )
                try:
                    with open(self.conf_file_path, "w") as f:
                        f.write(json.dumps(self.conf, indent=4))
                except Exception as e:
                    self.write_log(
                        "Error",
                        f"Failed to save username change to {self.conf_file_path}. {type(e)} {e}",
                    )
                    self.add_message(
                        "system",
                        "An error occurred while saving your username change, your new username will work for this session, but won't persist to next. Check uio.log for details.",
                    )
        else:
            self.add_message(self.conf["username"], self.in_buf)

    def format_msg_json(self, username: str, msg: str) -> str:
        """format a message as json with newlines and 4 space indenting.

        Args:
            username (str): The username.
            msg (str): The message content.

        Returns:
            str: The json formatted message.
        """
        return json.dumps([{"username": username, "message": msg}], indent=4)

    def split_to_strs(
        self, max_length: int, text: str, split_slash_n: bool = False
    ) -> tuple[str, ...]:
        lines = []
        line = ""

        i = 0
        while i in range(len(text)):
            char = text[i]

            # ---  TEACHING MOMENT :3  ---
            # The way python checks conditionals, it stops evaluating when an "and" is followed by something False,
            # so we can check if it's possible to index to i+1, before indexing to i+1, by checking with len() BEFORE slicing to find "\n",
            # this only works if, in our line of "and" statements, the confirmation that it's possible happens before we try.
            # Note: When string slicing, e.g. "str[a:b]", the char at index b is not included,
            # we want that last char, so it's [i:i+2], not [i:i+1] which would only give us the char at index i, excluding the char at index i+1.
            # --- TEACHING MOMENT OVER ---
            if split_slash_n and len(text) > i + 1 and text[i : i + 2] == "\\n":
                lines.append(line)
                line = ""
                i += 1
            elif len(line) < max_length:
                line += char
            else:
                lines.append(line)
                if char != " ":
                    line = char
                else:
                    line = ""
            i += 1

        if line != "":
            lines.append(line)

        return tuple(lines)

    def draw_screen(self) -> None:
        height, width = curses.LINES, curses.COLS
        self.stdscr.clear()

        # First, generate the lines that need to be drawn

        # lines will be drawn by putting the item at index 0 at the lowest line, index 1 at the second lowest, etc
        lines = []
        line = ""

        # start with the input area
        in_area_lines = list(self.split_to_strs(width - 2, "> " + self.in_buf))
        in_area_lines.reverse()

        for line in in_area_lines:
            lines.append(line)

        lines.append(f"{"─" * (width)}")

        # now the message history
        i = 0
        # dont want to edit msgs, so create a copy to reverse, note, just doing messages = msgs would make messages a pointer to msgs, not a copy
        messages = self.msgs[:]
        messages.reverse()
        while len(lines) < height - 1:
            if i >= len(messages):
                break
            msg = messages[i]
            base_str = f"<{msg["username"]}: {msg["message"]}"
            str_on_lines = list(
                self.split_to_strs(width - 1, base_str, split_slash_n=True)
            )
            str_on_lines.reverse()

            for line in str_on_lines:
                if len(lines) < height:
                    lines.append(line)

            i += 1

        # and now that we have a bunch of lines, we draw them
        for i, line in enumerate(lines):
            self.stdscr.addstr(height - i - 1, 0, line)
            if i == 0:
                cursor_yx = self.stdscr.getyx()

        self.stdscr.move(cursor_yx[0], cursor_yx[1])

    def add_message(
        self,
        username: str | Literal["system"],
        msg: str,
    ) -> None:
        self.msgs.append({"username": username, "message": msg})
        self.write_chat_history_file()

    def main(
        self,
        init_error_codes: str[int] = [],
    ) -> None:
        height, width = curses.LINES, curses.COLS
        self.write_log("Info", f"Entered main with height, width: {height}, {width}")

        if 1 in init_error_codes:
            self.add_message(
                "system",
                "Failed to load or create a .conf file. Check uio.log for details.",
            )

        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)

        self.in_buf = ""

        while True:
            self.draw_screen()

            # getkey refreshes the screen, and pauses the program until an input before proceeding
            c = self.stdscr.getkey()

            if c == "\n":
                # user pressed enter, parse and flush input buffer
                self.parse_input_buffer()
                self.in_buf = ""
            elif c == "\x08" or c == "KEY_BACKSPACE":
                # Backspace
                self.in_buf = self.in_buf[:-1]
            elif len(c) == 1:
                # user input a char, add it to buffer
                self.in_buf += c
            else:
                # user pressed an other non char key, just ignore it
                pass

    def exit(self) -> NoReturn:
        """exits the program, first explicitly closing any files that should be open and resetting the terminal to a useable state"""

        try:  # close uio.log if open
            self.uio_log.close()
        except:
            pass

        # im pretty sure just running curses.endwin() would do everything beyond this point anyway, but just to be safe lol

        try:
            curses.echo()
            curses.nocbreak()
            self.stdscr.keypad(False)
        except Exception as e:
            self.write_log(
                "Warning", f"Soft error during initial exit sequence. {type(e)} {e}"
            )

        curses.endwin()
        sys.exit()

    def write_chat_history_file(self) -> None:
        try:
            with open(self.conf["chat_history_path"], "w") as chat_history_file:
                chat_history_file.write(json.dumps(self.msgs, indent=4))
        except Exception as e:
            self.write_log(
                "Error",
                f'Failed to write a message to {self.conf["chat_history_path"]}, {type(e)} {e}',
            )

    def find_file(self, pattern: str, path: str) -> list[str]:
        """Finds a file in a directory recursively scanning subdirectories using a Unix shell style pattern.
        Credit to Nadia Alramli on stackoverflow for this cute little function, thanks :3
        Note: function renamed has been renamed, given a docstring, type hinting, and changed dirs to _.
        https://stackoverflow.com/a/1724723
        """
        result = []
        for root, _, files in os.walk(path):
            for name in files:
                if fnmatch(name, pattern):
                    result.append(os.path.join(root, name))
        return result

    def load_conf(self, conf_path: str | None = None) -> int:
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
