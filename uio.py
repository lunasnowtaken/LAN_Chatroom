# curses isn't included in windows python by default, to install it, run pip install windows-curses
# the python docs on curses are really useful https://docs.python.org/3/howto/curses.html would suggest
import curses
import time
from typing import Literal, NoReturn
import json


def write_log(err_level: Literal["FatalError", "Error", "Warning", "Info"], msg) -> int:
    """Writes something to uio.log in the format 'YYYY:MM:DD hh:mm:ss, {err_level}: "{msg}"\\n' and returns success.
    If global uio_log already exists, uses that, otherwise, opens uio.log as global uio_log, and uses that.

    Args:
        err_level (Literal["Error", "Warning", "Info"]): The log severity, can be 1 of the 3 offered values.
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
        write_log("Warning", f'Soft error during initial exit sequence. "{e}"')

    curses.endwin()


def draw_screen(
    stdscr: curses.window, msgs: list[tuple[str, str]], in_buf: str
) -> None:
    height, width = curses.LINES, curses.COLS
    stdscr.clear()

    input_offset = 0

    stdscr.addstr(height - 2 - input_offset, 0, f"{"─" * (width)}")
    stdscr.addstr(height - 1 - input_offset, 0, f"> {in_buf}")


def write_chat_history(
    stdscr: curses.window, msgs: list[dict[str:str, str:str]]
) -> None | NoReturn:
    try:
        with open(chat_history_file_path, "w") as chat_history_file:
            chat_history_file.write(json.dumps(msgs, indent=4))
    except Exception as e:
        write_log(
            "Error",
            f'Exiting after failure to write a message to {chat_history_file_path}, "{e}"',
        )
        exit_program(stdscr)


def parse_input_buffer(
    stdscr: curses.window,
    msgs: list[dict[str:str, str:str]],
    in_buf: str,
    username: str,
) -> None:
    if in_buf == "/exit":
        write_log("Info", "Exiting normally after /exit command")
        exit_program(stdscr)
    else:
        msgs.append({"username": username, "message": in_buf})
        write_chat_history(stdscr, msgs)


def format_msg_json(username: str, msg: str) -> str:
    """format a message as json with newlines and 4 space indenting.

    Args:
        username (str): The username.
        msg (str): The message content.

    Returns:
        str: The json formatted message.
    """
    return json.dumps([{"username": username, "message": msg}], indent=4)


def main(stdscr: curses.window, msgs) -> None:
    user_username = "default-username"
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
            parse_input_buffer(stdscr, msgs, in_buf, user_username)
            in_buf = ""
        elif c == "\x08":
            # Backspace
            in_buf = in_buf[:-1]
        elif len(c) == 1:
            # user input a char, add it to buffer
            in_buf += c
        else:
            # user pressed an other non char key.
            pass


# These should be defined and or globalised even if this file is imported as a module
global uio_log, uio_log_path, chat_history_file_path
uio_log_path = "uio.log"
chat_history_file_path = "LocalChatHistory.json"

if __name__ == "__main__":
    stdscr = curses.initscr()
    # uio_log is kept open, and only closed when program quits
    uio_log = open("uio.log", "a")

    # chat_history_file should be opened and then closed once a given operation is completed
    with open(chat_history_file_path, "+a") as chat_history_file:
        chat_history_file.seek(0)
        if chat_history_file.read() == "":
            chat_history_file.write(
                format_msg_json("system", "Welcome to LAN Chatroom")
            )

    # a list of dicts [{"username": str-username, "message": str-message},...]
    # note when chat history sharing is implemented, msgs with username "system" shouldn't be shared
    # and "system" should not be allowed as a username
    try:
        with open(chat_history_file_path, "r") as chat_history_file:
            chat_history_file.seek(0)
            msgs = json.loads(chat_history_file.read())
    except Exception as e:
        write_log(
            "Warning",
            f'Failed to load chat history form {chat_history_file_path}, proceeding with empty history. "{e}"',
        )
        msgs = [{"username": "system", "message": "Failed to load chat history."}]
        write_chat_history(stdscr, msgs)

    try:
        main(stdscr, msgs)
    except KeyboardInterrupt:
        write_log("Info", "Exiting normally after KeyboardInterrupt")
        exit_program(stdscr)
    except Exception as e:
        write_log(
            "FatalError",
            f'Exiting after an unexpected exception occurred. "{e}"',
        )
        exit_program(stdscr)
