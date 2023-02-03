import argparse
import os
import platform
from pathlib import Path

from termcolor import colored
from colorama import init

if __name__ == '__main__':
    python_command: str = "python.exe" if platform.system() == "Windows" else "python"
    flush_command: str = "cls"
    init()
    parser = argparse.ArgumentParser(
        description='Execute the analyzer against a folder of smart-contracts')
    parser.add_argument('-f', "--folder", required=True, help="Path of a solidity source code file")
    folder_path = Path(parser.parse_args().folder)
    if not folder_path.exists() or not folder_path.is_dir():
        print(colored(f"{folder_path.name} is not a folder!", "red"))
    try:
        for file in folder_path.glob("**/*.sol"):
            os.system(f"{flush_command} && {python_command} ../analyzer.py -v -ap -a analyze -t \"{file}\"")
            input("Press Enter to continue...")
            os.system(f"{flush_command} && {python_command} ../analyzer.py -v -ap -a describe -t \"{file}\"")
            input("Press Enter to continue...")
    except KeyboardInterrupt:
        print("Interrupt by user")
