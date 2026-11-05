import sys
import logging
from pathlib import Path

try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    BLUE = Fore.BLUE
    RED = Fore.RED
    CYAN = Fore.CYAN
    GREEN = Fore.GREEN
    RESET = Style.RESET_ALL
except ImportError:
    BLUE = RED = CYAN = GREEN = RESET = ""


def file_input_string() -> str:
    return input("\n ENTER FILE PATH > ").strip()


def output_path_string() -> str:
    return input("\n ENTER OUTPUT PATH > ").strip()


def option(min_val: int, max_val: int) -> int:
    selection = input("\n ENTER INPUT > ").strip()
    try:
        num = int(selection)
    except ValueError:
        print(RED + "  [!] INVALID INPUT" + RESET)
        return option(min_val, max_val)

    if num == min_val:
        print(BLUE + " Farewell and fly high!" + RESET)
        sys.exit(1)
    elif num == max_val - 1:
        return -1
    elif min_val < num <= max_val:
        return num
    else:
        print(RED + "  [!] INVALID INPUT" + RESET)
        return option(min_val, max_val)


def check_file_format(path: str, exten: str) -> bool:
    return Path(path).suffix.lower() == exten


def gen_table_header(name: str, contain_break: bool = True):
    prefix = "\n" if contain_break else ""
    print(BLUE + prefix + "    ╔══════════════════════════════════════════════════════════════════════════════╗" + RESET)
    amount = (78 - len(name)) // 2
    extra_padding = 1 if len(name) % 2 != 0 else 0
    print(BLUE + "    ║" + " " * amount + name + " " * (amount + extra_padding) + "║" + RESET)
    print(BLUE + "    ╠══════════════════════════════════════════════════════════════════════════════╣" + RESET)


def gen_table_header_modified(name: str):
    print(BLUE + "    ╠══════════════════════════════════════════════════════════════════════════════╣" + RESET)
    amount = (78 - len(name)) // 2
    extra_padding = 1 if len(name) % 2 != 0 else 0
    print(BLUE + "    ║" + " " * amount + name + " " * (amount + extra_padding) + "║" + RESET)
    print(BLUE + "    ╠══════════════════════════════════════════════════════════════════════════════╣" + RESET)


def gen_row_string(intro: str, input_val: str):
    total_count = 4 + len(intro) + len(input_val) + 2
    use_count = max(0, 80 - total_count)
    val = "    ║ " + intro + ": " + input_val + " " * use_count + " ║"
    print(BLUE + val + RESET)


def gen_table_footer():
    print(BLUE + "    ╚══════════════════════════════════════════════════════════════════════════════╝" + RESET)


def print_log(message: str):
    print(CYAN + message + RESET)


def print_error(message: str):
    print(RED + "[ERROR] " + message + RESET)


def print_error_log(message: str, err: Exception):
    print(RED + message + RESET)
    logging.error("[ERROR] %s", str(err))


def print_valid_log(message: str):
    print(GREEN + message + RESET)


def print_invalid_log(message: str):
    print(RED + message + RESET)


def execute_parser(index: int):
    from parsers import DJI_CSV_Parser, DJI_KML_Parser, DJI_GPX_Parser
    file_path = file_input_string()
    if index == 1:
        DJI_CSV_Parser(file_path).parse_contents()
    elif index == 2:
        DJI_KML_Parser(file_path).parse_contents()
    elif index == 3:
        DJI_GPX_Parser(file_path).parse_contents()
