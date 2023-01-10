import argparse
import json
import logging

from pathlib import Path
from termcolor import colored

from modules.config import settings


def bootstrap(default_descriptor: Path) -> dict[str, str]:
    """
    This function parses the user's input and, if validated, return them in a dictionary
    :param default_descriptor: Path to the default descriptor folder
    :return: A dictionary containing the validated data
    """
    parser = argparse.ArgumentParser(
        description='A cli utility that performs a static analysis of solidity source code to find design patterns '
                    'implementations',
        epilog=f"Version: {settings.version} - Developed by Alessio Tudisco for Bachelor Thesis")
    parser.add_argument("-a", "--action", required=True, choices=["analyze", "describe"],
                        help="A solidity source file can be analyzed to find design pattern implementations or "
                             "described to create a generic descriptor")
    parser.add_argument('-t', "--target", required=True, help="Path of a solidity source code file")
    parser.add_argument('-d', "--descriptor", required=False, default=default_descriptor,
                        help="Path of a Design Pattern descriptor or a folder containing them")
    parser.add_argument('-v', '--verbose', required=False, help="For debugging purpose, show all the intermediate logs",
                        action='store_true')
    parser.add_argument('-ai', '--allow-incompatible', required=False, help="Bypass the solidity version incompatible "
                                                                            "prompt", action='store_true')
    parser.add_argument('-ap', '--auto-plot', required=False, help="Automatically plots the results",
                        action='store_true')
    inputs: dict[str, str] = vars(parser.parse_args())
    settings.verbose = inputs["verbose"]
    settings.allow_incompatible = inputs["allow_incompatible"]
    settings.auto_plot = inputs["auto_plot"]
    del inputs["verbose"]
    del inputs["allow_incompatible"]
    del inputs["auto_plot"]
    inputs["schema"] = settings.schema_path
    if not is_input_valid(inputs):
        exit(-1)
    return inputs


def is_input_valid(inputs: dict[str, str]) -> bool:
    """
    This functions checks if the user's input is valid
    :param inputs: A dictionary containing the user's input
    :return: True if the inputs are valid, False otherwise
    """
    for input_type, input_value in inputs.items():
        if input_type == "action":
            continue
        input_path = Path(input_value)
        error: str = ""
        if settings.verbose:
            logging.debug("%s '%s'", colored(f"Checking {input_type}:", "blue"), colored(input_value, "cyan"))
        if not input_path.exists():
            error = f"The input '{input_value}' does not exist, aborting..."
        elif input_type == "target" or input_type == "schema":
            if not input_path.is_file():
                error = f"The input '{input_value}' is not a file, aborting..."
            elif input_type == "target" and not input_path.name.split(".")[-1] == "sol":
                error = f"The input '{input_value}' is not a solidity source code file, aborting..."
            elif input_type == "schema" and not input_path.name.split(".")[-1] == "json":
                error = f"The input '{input_value}' is not a json schema file, aborting..."
        else:
            if input_path.is_file() and not input_path.name.split(".")[-1] == "json":
                error = f"The input '{input_value}' is not a design pattern descriptor json file, aborting..."
        if error:
            logging.error(colored(error, "red"))
            return False
    if settings.verbose:
        logging.debug(colored("The user's input has been validated successfully, ready to operate!", "green"))
    return True


def ask_confirm(question_text: str) -> bool:
    """
    This function asks a yes/no query to the user
    :param question_text: A yes/no query for the user
    :return: True if it is confirmed, False otherwise
    """
    while True:
        try:
            answer: str = input(colored(f"{question_text} [y/n]: ", "magenta")).lower()
            if answer == "y":
                return True
            elif answer == "n":
                return False
        except KeyboardInterrupt:
            print("\n")  # Fixes no new line after input's prompts
            logging.info(colored("KeyboardInterrupt intercepted, aborting...", "yellow"))
            return False


def save_analysis_results(target: str, results: dict[str, dict[str, dict[str, bool]]]) -> None:
    """
    This function saves to the disk the analysis's results
    :param target: The solidity source code path
    :param results: A dictionary containing the results of the static analysis
    """
    target_path: Path = Path(target)
    output_path: Path = Path(f"{target_path.parent}/results_{target_path.stem}.json")
    try:
        with open(output_path, "w") as output_fp:
            output_fp.write(json.dumps(results))
            logging.info("%s '%s'", colored("Results saved to:", "green"), colored(str(output_path), "cyan"))
    except IOError as fp_error:
        logging.error(colored(f"Unable to save results to: '{output_path}'\n{fp_error}", "red"))


def save_describe_results(target: str, results: dict[str, list[dict]]) -> None:
    """
    This function saves to the disk the smart-contract's describe results
    :param target: The solidity source code path
    :param results: A dictionary containing the generated descriptors
    """
    target_path: Path = Path(target)
    for descriptor_name, descriptor_checks in results.items():
        output_path: Path = Path(f"{target_path.parent}/{descriptor_name}_descriptor.json")
        descriptor: dict = {
            "name": descriptor_name,
            "checks": descriptor_checks
        }
        try:
            with open(output_path, "w") as output_fp:
                output_fp.write(json.dumps(descriptor))
                logging.info("%s '%s'", colored("Descriptor saved to:", "green"), colored(str(output_path), "cyan"))
        except IOError as fp_error:
            logging.error(colored(f"Unable to save descriptor to: '{output_path}'\n{fp_error}", "red"))


def format_analysis_results(results: dict[str, dict[str, dict[str, bool]]]) -> str:
    """
    Formats the results on the terminal
    :param results: A dictionary containing the results of the static analysis
    :return: A formatted string to display results
    """
    styled_results: str = colored("\n|--- Results ---|\n\n", "green")
    for smart_contract, descriptors in results.items():
        styled_results = f"{styled_results}{colored('Smart-Contract: ', 'green')}{colored(smart_contract, 'yellow')}\n"
        for descriptor, checks in descriptors.items():
            passed_tests: int = sum(checks.values())
            styled_results = f'{styled_results}\t{colored("Descriptor: ", "green")}{colored(descriptor, "yellow")}' \
                             f'\n\t\tMay {"be" if passed_tests > 0 else "be not"} used ' \
                             f'({colored(str(passed_tests), "magenta")} checks passed)\n'
            for check, validated in checks.items():
                styled_results = f"{styled_results}\t\t\tTest '{colored(check, 'yellow')}':\t" \
                                 f"{colored('passed', 'green') if validated else colored('failed', 'red')}\n"
    return styled_results
