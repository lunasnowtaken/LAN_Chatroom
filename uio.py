# curses isn't included in windows python by default, to install it, run pip install windows-curses
# the python docs on curses are really useful https://docs.python.org/3/howto/curses.html would suggest
import curses
import time
from typing import Literal, NoReturn
import json
import sys
import os
from fnmatch import fnmatch


def write_log(
    err_level: str | Literal["FatalError", "Error", "Warning", "Info"], msg
) -> int:
    """Writes something to uio.log in the format 'YYYY:MM:DD hh:mm:ss, {err_level}: "{msg}"\\n' and returns success.
    If global uio_log already exists, uses that, otherwise, opens uio.log and uses that.

    Args:
        err_level (Literal["FatalError", "Error", "Warning", "Info"]): The log severity, should be 1 of the 4 offered options, can be an any str.
        msg (str): The message to write.

    Returns:
        int: Errors, 0 if writing succeeded with no errors, 1 if it failed
    """
    log_msg = f"{time.strftime("%Y/%m/%d %H:%M:%S")}, {err_level}: '{msg}'\n"
    try:
        uio_log.write(log_msg)
        return 0
    except:
        try:
            uio_log = open(uio_log_path, "a")
            uio_log.write(log_msg)
            return 0
        except:
            return 1


def exit_program(stdscr: curses.window) -> NoReturn:
    """exits the program, first explicitly closing any files that should be open and resetting the terminal to a useable state"""

    try:  # close uio.log if open
        uio_log.close()
    except:
        pass

    # im pretty sure just running curses.endwin() would do everything beyond this point anyway, but just to be safe lol

    try:
        curses.echo()
        curses.nocbreak()
        stdscr.keypad(False)
    except Exception as e:
        write_log("Warning", f'Soft error during initial exit sequence. {type(e)} {e}')

    curses.endwin()
    sys.exit()


def split_to_strs(
    max_length: int, text: str, split_slash_n: bool = False
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


def draw_screen(
    stdscr: curses.window, msgs: list[dict[str:str, str:str]], in_buf: str
) -> None:
    height, width = curses.LINES, curses.COLS
    stdscr.clear()

    # First, generate the lines that need to be drawn

    # lines will be drawn by putting the item at index 0 at the lowest line, index 1 at the second lowest, etc
    lines = []
    line = ""

    # start with the input area
    in_area_lines = list(split_to_strs(width - 2, "> " + in_buf))
    in_area_lines.reverse()
    # ial_len = len(in_area_lines)

    for line in in_area_lines:
        lines.append(line)

    lines.append(f"{"─" * (width)}")

    # now the message history
    i = 0
    # dont want to edit msgs, so create a copy to reverse, note, just doing messages = msgs would make messages a pointer to msgs, not a copy
    messages = msgs[:]
    messages.reverse()
    while len(lines) < height - 1:
        if i >= len(messages):
            break
        msg = messages[i]
        base_str = f"<{msg["username"]}: {msg["message"]}"
        str_on_lines = list(split_to_strs(width - 1, base_str, split_slash_n=True))
        str_on_lines.reverse()

        for line in str_on_lines:
            if len(lines) < height:
                lines.append(line)

        i += 1

    # and now that we have a bunch of lines, we draw them
    for i, line in enumerate(lines):
        stdscr.addstr(height - i - 1, 0, line)
        if i == 0:
            cursor_yx = stdscr.getyx()

    stdscr.move(cursor_yx[0], cursor_yx[1])


def write_chat_history_file(
    stdscr: curses.window, msgs: list[dict[str:str, str:str]]
) -> None | NoReturn:
    try:
        with open(conf["chat_history_path"], "w") as chat_history_file:
            chat_history_file.write(json.dumps(msgs, indent=4))
    except Exception as e:
        write_log(
            "Error",
            f'Failed to write a message to {conf["chat_history_path"]}, {type(e)} {e}',
        )


def add_message(
    stdscr: curses.window,
    msgs: list[dict[str:str, str:str]],
    username: str | Literal["system"],
    msg: str,
) -> None:
    msgs.append({"username": username, "message": msg})
    write_chat_history_file(stdscr, msgs)


def parse_input_buffer(
    stdscr: curses.window,
    msgs: list[dict[str:str, str:str]],
    in_buf: str,
) -> None:
    if in_buf.lower() == "/exit":
        write_log("Info", "Exiting normally after /exit command")
        exit_program(stdscr)
    elif in_buf.lower() == "/clear":
        try:
            chat_history_file = open(conf["chat_history_path"], "r")
            chat_history_file.seek(0)
            contents = chat_history_file.read()
            chat_history_file.close()

            # im unsure how the history file could be empty while msgs is not empty, but just in case
            if contents == "" and msgs == []:
                write_log(
                    "Info", f'No chat history to clear at {conf["chat_history_path"]}'
                )
            else:
                with open(conf["chat_history_path"], "w"):
                    msgs.clear()
                    write_log(
                        "Info", f'Cleared chat history at {conf["chat_history_path"]}'
                    )
                    # Opening in write mode truncates the file first, so nothing else to do
        except Exception as e:
            write_log(
                "Error",
                f'Failed to clear chat history at {conf["chat_history_path"]} {type(e)} {e}',
            )
    elif in_buf[0:9].lower() == "/username":
        # takes as argument a new username for the user, if given no username, tells users current username

        # remove the "/username" part
        in_buf = in_buf[9:]
        # remove any whitespace
        in_buf = in_buf.replace(" ", "")
        if in_buf == "":
            # no new username given, echo current username
            add_message(
                stdscr,
                msgs,
                "system",
                f"Your username is: {conf["username"]}\\n To change, use /username <new_username>",
            )
        elif in_buf == "system":
            add_message(
                stdscr,
                msgs,
                "system",
                'Your username cannot be "system"',
            )
        else:
            conf["username"] = in_buf
            add_message(stdscr, msgs, "system", f"Changed username to {in_buf}")
            try:
                with open(conf_file_path, "w") as f:
                    f.write(json.dumps(conf, indent=4))
            except Exception as e:
                write_log(
                    "Error", f"Failed to save username change to {conf_file_path}. {type(e)} {e}"
                )
                add_message(
                    stdscr,
                    msgs,
                    "system",
                    "An error occurred while saving your username change, your new username will work for this session, but won't persist to next. Check uio.log for details.",
                )
    else:
        add_message(stdscr, msgs, conf["username"], in_buf)


def format_msg_json(username: str, msg: str) -> str:
    """format a message as json with newlines and 4 space indenting.

    Args:
        username (str): The username.
        msg (str): The message content.

    Returns:
        str: The json formatted message.
    """
    return json.dumps([{"username": username, "message": msg}], indent=4)


def find_file(pattern: str, path: str) -> list[str]:
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


def load_conf(conf_path: str | None = None) -> int:
    """Loads the file at the specified file path as a config, or attempts to find or create a .conf to load instead.

    Args:
        conf_path (str | None, optional): The path to a .conf file to load. When None or not given, automatically finds or creates a .conf

    Returns:
        int: for conf_path = None: 0 if no errors, 1 if failed to load or create a conf, 2 if failed to load but successfully created a conf.
             for conf_path = str: 0 if no errors, 1 if failed to load conf
    """
    # TODO: Finish this
    global conf, conf_file_path
    conf_file_path = None
    config_success = -1
    if conf_path == None:
        configs: list[str] = find_file("*.conf", ".")
        if len(configs) == 0:
            # no conf found, make one
            write_log("Info", f"No config file found, attempting to create user.conf")
            try:
                with open("user.conf", "w") as f:
                    conf = {
                        "username": "anonymous",
                        "chat_history_path": "LocalChatHistory.json",
                    }
                    f.write(json.dumps(conf, indent=4))
                    conf_file_path = "user.conf"
                    write_log("Info", "Successfully created user.conf")
                    config_success = 0
            except Exception as e:
                # couldn't make one, proceed without
                write_log(
                    "Error",
                    f"Failed to create config file user.conf, proceeding without a conf file. {type(e)} {e}",
                )
                conf = {
                    "username": "anonymous",
                    "chat_history_path": "LocalChatHistory.json"
                }
                config_success = 1
        else:
            # we found one or more conf, try to use them
            for config in configs:
                write_log(
                    "Info",
                    f"found {len(configs)} conf file{"s" if len(configs) > 1 else ""}, trying {config}",
                )
                try:
                    with open(config, "r") as f:
                        f.seek(0)
                        contents = f.read()
                        conf = json.loads(contents)
                        conf_file_path = config
                        config_success = 0
                        break
                except Exception as e:
                    # couldn't use that conf,
                    write_log(
                        "Error",
                        f"Failed to load config file at {config} {type(e)} {e}",
                    )
            if config_success != 0:
                write_log(
                    "Info",
                    "Unable to load any of the found config files, attempting to make one.",
                )
                try:
                    with open("user.conf", "w") as f:
                        conf = {
                            "username": "anonymous",
                            "chat_history_path": "LocalChatHistory.json"
                        }
                        f.write(json.dumps(conf, indent=4))
                        conf_file_path = "user.conf"
                        write_log("Info", f"Successfully created config file user.conf")
                        config_success = 2
                except Exception as e:
                    # couldn't make one, proceed without
                    write_log(
                        "Error",
                        f"Failed to create config file user.conf, proceeding without a conf file. {type(e)} {e}",
                    )
                    conf = {
                        "username": "anonymous",
                        "chat_history_path": "LocalChatHistory.json"
                    }
                    config_success = 1
    else:
        write_log(
            "Info",
            f"Attempting to load config file {conf_path}",
        )
        try:
            with open(conf_path, "r") as f:
                f.seek(0)
                contents = f.read()
                conf = json.loads(contents)
                conf_file_path = conf_path
                config_success = 0
        except Exception as e:
            # couldn't use that conf,
            write_log(
                "Error",
                f"Failed to load config file at {config} {type(e)} {e}",
            )
            config_success = 1

    conf["chat_history_path"] = conf["chat_history_path"]

    return config_success


def main(
    stdscr: curses.window,
    msgs: list[dict[str:str, str:str]],
    init_error_codes: str[int] = [],
) -> None:
    height, width = curses.LINES, curses.COLS
    write_log("Info", f"Program launched with height, width: {height}, {width}")

    if 1 in init_error_codes:
        add_message(
            stdscr,
            msgs,
            "system",
            "Failed to load or create a .conf file. Check uio.log for details.",
        )
    elif 2 in init_error_codes:
        add_message(
            stdscr,
            msgs,
            "system",
            "Failed to load .conf file, created a new file. Check uio.log for details.",
        )

    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)

    in_buf = ""

    while True:
        draw_screen(stdscr, msgs, in_buf)

        # getkey refreshes the screen, and pauses the program until an input before proceeding
        c = stdscr.getkey()

        if c == "\n":
            # user pressed enter, parse and flush input buffer
            parse_input_buffer(stdscr, msgs, in_buf)
            in_buf = ""
        elif c == "\x08" or c == "KEY_BACKSPACE":
            # Backspace
            in_buf = in_buf[:-1]
        elif len(c) == 1:
            # user input a char, add it to buffer
            in_buf += c
        else:
            # user pressed an other non char key, just ignore it
            pass


if __name__ == "__main__":
    stdscr = curses.initscr()
    # uio_log is kept open, and only closed when program quits, this is so we can
    global uio_log, uio_log_path
    uio_log_path = "uio.log"
    uio_log = open(uio_log_path, "a")

    error_codes = []
    conf_success = load_conf()
    if conf_success != 0:
        error_codes.append(conf_success)

    try:
        with open(conf["chat_history_path"], "+a") as f:
            f.seek(0)
            contents = f.read()
            if contents == "":
                f.write("[]\n")
    except Exception as e:
        write_log(
            "Error",
            f'Failed to open or create chat history file at {conf["chat_history_path"]}, attempting to proceed without. {type(e)} {e}',
        )
        msgs = [{"username": "system", "message": "Failed to load chat history."}]
        write_chat_history_file(stdscr, msgs)

    # msgs is a list of dicts [{"username": str-username, "message": str-message},...]
    # note when chat history sharing is implemented, msgs with username "system" shouldn't be shared
    # and "system" should not be allowed as a username
    try:
        with open(conf["chat_history_path"], "r") as f:
            f.seek(0)
            msgs = json.loads(f.read())
    except Exception as e:
        write_log(
            "Error",
            f'Failed to load chat history at {conf["chat_history_path"]}, proceeding with empty history. {type(e)} {e}',
        )
        msgs = [{"username": "system", "message": "Failed to load chat history."}]
        write_chat_history_file(stdscr, msgs)

    try:
        main(stdscr, msgs, error_codes)
    except KeyboardInterrupt:
        write_log(
            "Info",
            "Exiting normally after KeyboardInterrupt (usually occurs after pressing ctrl+c)",
        )
        exit_program(stdscr)
    except Exception as e:
        write_log(
            "FatalError",
            f'Exiting after an unexpected exception occurred. {type(e)} {e}',
        )
        exit_program(stdscr)
