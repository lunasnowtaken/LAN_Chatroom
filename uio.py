# curses isn't included in windows python by default, to install it, run pip install windows-curses
# the python docs on curses are really useful https://docs.python.org/3/howto/curses.html would suggest
import curses
from curses import wrapper
import time
from typing import Literal
import json


def write_log(err_level: Literal["Error", "Warning", "Info"], msg) -> int:
    """Writes something to uio.log in the format 'YYYY:MM:DD hh:mm:ss, {err_level}: "{msg}"\\n' and returns success.
    If global uio_log already exists, uses that, otherwise, opens uio.log as global uio_log, and uses that.

    Args:
        err_level (Literal["Error", "Warning", "Info"]): The log severity, can be 1 of the 3 offered values.
        msg (str): The message to write.

    Returns:
        int: Errors, 0 if writing succeeded with no errors, 1 if it failed
    """
    try:
        uio_log.write(f'{time.strftime("%Y/%m/%d %H:%M:%S")}, {err_level}: "{msg}"\n')
        return 0
    except:
        try:
            uio_log = open("uio.log", "a")
            uio_log.write(
                f'{time.strftime("%Y/%m/%d %H:%M:%S")}, {err_level}: "{msg}"\n'
            )
            return 0
        except:
            return 1


def exit_program(stdscr: curses.window) -> None:
    """exits the program, first closing all files and resetting the terminal to a useable state"""

    try:  # close ChatHistory.json if open
        chat_history_file.close()
    except:
        pass
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


def parse_input_buffer(msgs: list[tuple[str, str]], in_buf: str, username: str) -> None:

    msgs.append((username, in_buf))
    
    chat_history_file.write()
    chat_history_file.close()


def format_msg_json(username: str, msg: str) -> str:
    """format a message as json with newlines and 4 space indenting.

    Args:
        username (str): The username.
        msg (str): The message content.

    Returns:
        str: The json formatted message.
    """
    return json.dumps([{"username": username, "message": msg}], indent=4)


def main(stdscr: curses.window) -> None:
    user_username = "default-username"
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)

    # a list of tuples [(str-username, str-message),...]
    # note when chat history sharing is implemented, msgs with username "system" shouldn't be shared
    # and "system" should not be allowed as a username
    messages: list[tuple[str, str]] = [
        ("system", "Welcome to lan chatroom"),
    ]

    in_buf = ""

    while True:
        draw_screen(stdscr, messages, in_buf)

        # getkey refreshes the screen, and pauses the program until an input before proceeding
        c = stdscr.getkey()

        if c == "\n":
            # user pressed enter, parse and flush input buffer
            parse_input_buffer(messages, in_buf, user_username)
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


if __name__ == "__main__":
    stdscr = curses.initscr()
    global uio_log
    uio_log = open("uio.log", "a")

    global chat_history_file
    chat_history_file = open("LocalChatHistory.json", "+a")
    chat_history_file.seek(0)
    if chat_history_file.read() == "":
        chat_history_file.write(format_msg_json("system", "Welcome to LAN Chatroom"))

    try:
        main(stdscr)
    except KeyboardInterrupt:
        write_log("Info", "Exiting normally after KeyboardInterrupt")
        exit_program(stdscr)
    except Exception as e:
        write_log(
            "Error",
            f'Exiting with errors after an unexpected exception occurred. "{e}"',
        )
        exit_program(stdscr)
