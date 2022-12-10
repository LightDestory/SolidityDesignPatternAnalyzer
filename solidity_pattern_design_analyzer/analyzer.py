import argparse
import logging
from pathlib import Path

from colorama import init
from termcolor import colored

from modules.config import settings
from modules.descriptor_validator import DescriptorValidator
from modules.solidity_scanner import SolidityScanner

logging.basicConfig(format='%(levelname)s:\t%(message)s', level=logging.DEBUG)


def bootstrap(default_schema: str, default_descriptor: str) -> dict[str, str]:
    """
    This function parses the user's input and, if validated, return them in a dictionary
    :param default_schema: Path to the default schema
    :param default_descriptor: Path to the default descriptor folder
    :return: A dictionary containing the validated data
    """
    parser = argparse.ArgumentParser(
        description='A cli utility that performs a static analysis of solidity source code to find design patterns '
                    'usage',
        epilog="Version: {} - Developed by Alessio Tudisco for Bachelor Thesis".format(settings.version))
    parser.add_argument('-t', "--target", required=True, help="Path of a solidity source code file")
    parser.add_argument('-s', "--schema", required=False, default=default_schema,
                        help="Path of a JSON-Schema to validate descriptors")
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
        input_path = Path(input_value)
        if settings.verbose:
            logging.debug(colored("Checking {}: '{}' ...".format(input_type, input_path), "blue"))
        if not input_path.exists():
            logging.error(colored("The input '{}' does not exist, aborting...".format(input_value), "red"))
            return False
        if input_type == "target" or input_type == "schema":
            if not input_path.is_file():
                logging.error(colored("The input '{}' is not a file, aborting...".format(input_value), "red"))
                return False
            if input_type == "target" and not input_path.name.split(".")[-1] == "sol":
                logging.error(colored("The input '{}' is not a solidity source code file, aborting..."
                                      .format(input_value), "red"))
                return False
            if input_type == "schema" and not input_path.name.split(".")[-1] == "json":
                logging.error(colored("The input '{}' is not a json schema file, aborting..."
                                      .format(input_value), "red"))
                return False
        else:
            if input_path.is_file() and not input_path.name.split(".")[-1] == "json":
                logging.error(colored("The input '{}' is not a design pattern descriptor json file, aborting..."
                                      .format(input_value), "red"))
                return False
    if settings.verbose:
        logging.debug(colored("The user's input has been validated successfully, ready to operate!", "green"))
    return True


def save_results(target: str, results: dict[str, dict[str, int]]) -> None:
    # TO-DO
    return


def print_results(results: dict[str, dict[str, int]]) -> None:
    """
    Formats and prints the results on the terminal
    :param results: A dictionary containing the results of the static analysis
    :return:
    """
    styled_results: str = colored("\n|--- Results ---|\n\n", "green")
    for smart_contract in results.keys():
        styled_results = "{}{}{}\n".format(styled_results, colored("Smart-Contract: ", "green"),
                                           colored(smart_contract, "yellow"))
        for descriptor, passed_tests in results[smart_contract].items():
            styled_results = "{}\t{}{}\n\t\tMay {} used ({} checks passed)\n" \
                .format(styled_results, colored("Descriptor: ", "green"), colored(descriptor, "yellow"),
                        "be" if passed_tests > 0 else "be not", colored(str(passed_tests), "magenta"))
    logging.info(styled_results)


def main() -> None:
    inputs: dict[str, str] = bootstrap(default_schema="./modules/data/descriptor_schema.json",
                                       default_descriptor="./descriptors/")
    desc_validator = DescriptorValidator(inputs["descriptor"])
    logging.info(colored("Loading schema...", "yellow"))
    if not desc_validator.load_schema(schema_path=inputs["schema"]):
        exit(-1)
    logging.info(colored("Loading descriptors...", "yellow"))
    descriptors: list[dict] = desc_validator.load_descriptors()
    if not descriptors:
        exit(-1)
    scanner: SolidityScanner = SolidityScanner(descriptors=descriptors)
    logging.info(colored("Parsing solidity file...", "yellow"))
    if not scanner.parse_solidity_file(solidity_file_path=inputs["target"]):
        exit(-1)
    logging.info(colored("Checking solidity version...", "yellow"))
    if not scanner.is_version_compatible():
        exit(-1)
    logging.info(colored("Searching for design patterns...", "yellow"))
    analysis_results: dict[str, dict[str, int]] = scanner.get_design_pattern_statistics()
    print_results(analysis_results)
    save_results(inputs["target"], analysis_results)


if __name__ == '__main__':
    init()
    main()
