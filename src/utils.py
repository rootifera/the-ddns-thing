"""
This is just for colouring. I could use termcolor, I know
"""


def print_cyan(text):
    print(f"\033[96m{text}\033[0m")  # Cyan


def print_blue(text):
    print(f"\033[94m{text}\033[0m")  # Blue


def print_green(text):
    print(f"\033[92m{text}\033[0m")  # Green


def print_orange(text):
    print(f"\033[93m{text}\033[0m")  # Orange


def print_red(text):
    print(f"\033[91m{text}\033[0m")  # Red
