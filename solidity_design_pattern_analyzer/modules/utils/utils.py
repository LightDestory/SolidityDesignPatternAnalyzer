import argparse
import datetime
import json
import logging

from pathlib import Path
from termcolor import colored

from ..config import settings


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
    parser.add_argument('-t', "--target", required=True, help="Path of a solidity source code file or "
                                                              "a directory containing them")
    parser.add_argument('-d', "--descriptor", required=False, default=default_descriptor,
                        help="Path of a Design Pattern descriptor or a folder containing them")
    parser.add_argument('-v', '--verbose', required=False, help="For debugging purpose, show all the intermediate logs",
                        action='store_true')
    parser.add_argument('-ai', '--allow-incompatible', required=False, choices=["ask", "skip", "always"],
                        help="Bypass the solidity version incompatible prompt", default="ask")
    parser.add_argument('-p', '--plot', required=False, choices=["ask", "skip", "always"],
                        help="Plotting Behaviour, choice between ask for confirm, skip or plot always", default="ask")
    parser.add_argument("-pr", "--print-result", required=False, help="Print a results' summary on the terminal",
                        action='store_true')
    parser.add_argument('-ws', '--write-result', required=False, choices=["ask", "skip", "always"],
                        help="Save the computational result on disk", default="ask")
    parser.add_argument('-rf', '--result-format', required=False, choices=["json", "csv"],
                        help="Result's format of the 'analyze' computation', CSV or JSON", default="json")
    inputs: dict[str, str] = vars(parser.parse_args())
    settings.execution_mode = inputs["action"]
    settings.result_format = inputs["result_format"]
    settings.verbose = inputs["verbose"]
    settings.allow_incompatible = inputs["allow_incompatible"]
    settings.plot = inputs["plot"]
    settings.print_result = inputs["print_result"]
    settings.write_result = inputs["write_result"]
    if inputs["action"] == "describe":
        del inputs["descriptor"]
    else:
        inputs["schema"] = settings.schema_path
    del inputs["action"]
    del inputs["result_format"]
    del inputs["verbose"]
    del inputs["allow_incompatible"]
    del inputs["plot"]
    del inputs["print_result"]
    del inputs["write_result"]
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
        error: str = ""
        if settings.verbose:
            logging.debug("%s '%s'", colored(f"Checking {input_type}:", "blue"), colored(input_value, "cyan"))
        if not input_path.exists():
            error = f"The input '{input_value}' does not exist, aborting..."
        elif input_type == "schema":
            if not input_path.is_file() or not input_path.name.split(".")[-1] == "json":
                error = f"The Descriptor Schema must be a json schema file, aborting..."
        elif input_type == "target" or input_type == "descriptor":
            file_extension: str = "sol" if input_type == "target" else "json"
            if input_path.is_file():
                if not input_path.name.split(".")[-1] == file_extension:
                    error = f"The input '{input_value}' is not a {file_extension} file, aborting..."
            else:
                if input_type == "target":
                    settings.batch_mode = True
                if not any(file.name.split(".")[-1] == file_extension for file in
                           input_path.glob(f"**/*.{file_extension}")):
                    error = (f"The input '{input_value}' directory does not contain any .{file_extension} file, "
                             "aborting...")
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
    output_path: Path = Path(f"{target_path.parent}/results_{target_path.stem}.{settings.result_format}")
    try:
        with open(output_path, "w") as output_fp:
            if settings.result_format == "json":
                output_fp.write(json.dumps(results))
            else:
                csv_lines: list[str] = []
                output_fp.write(get_csv_columns() + "\n")
                for contract_name, contract_results in results.items():
                    tmp: str = f"{target_path.name},{contract_name}"
                    for _, pattern_design_results in dict(sorted(contract_results.items())).items():
                        tmp += f",{any(x == True for x in pattern_design_results.values())}"
                    csv_lines.append(tmp+"\n")
                output_fp.writelines(csv_lines)
            logging.info("%s '%s'", colored("Results saved to:", "green"), colored(str(output_path), "cyan"))
    except IOError as fp_error:
        logging.error(colored(f"Unable to save results to: '{output_path}'\n{fp_error}", "red"))


def save_batch_analysis_results(results_wrapper: dict[str, dict[str, dict[str, dict[str, bool]]]], batch_save_dir: Path) -> None:
    """
    This function saves to the disk the batch analysis's results
    :param results_wrapper: A wrapper containing the results of the static analysis indexed by the solidity file path
    :param batch_save_dir: Folder where to save the batch results
    """
    timestamp: str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_path: Path = Path(f"{batch_save_dir}/batch_{timestamp}.{settings.result_format}")
    try:
        with open(output_path, "w") as output_fp:
            if settings.result_format == "csv":
                output_fp.write(get_csv_columns() + "\n")
            else:
                output_fp.write("[\n")
            _counter = 0
            for target_path, results in results_wrapper.items():
                target_path = Path(target_path)
                if settings.result_format == "json":
                    output_fp.write(json.dumps({target_path.name: results}))
                    if _counter < len(results_wrapper)-1:
                        output_fp.write(",\n")
                        _counter += 1
                else:
                    csv_lines: list[str] = []
                    for contract_name, contract_results in results.items():
                        tmp: str = f"{target_path.name},{contract_name}"
                        for _, pattern_design_results in dict(sorted(contract_results.items())).items():
                            tmp += f",{any(x == True for x in pattern_design_results.values())}"
                        csv_lines.append(tmp+"\n")
                    output_fp.writelines(csv_lines)
            if settings.result_format == "json":
                output_fp.write("\n]")
            logging.info("%s '%s'", colored("Batch Results saved to:", "green"), colored(str(output_path), "cyan"))
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


def terminal_result_formatter(results: dict[str, dict[str, dict[str, bool]]]) -> str:
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


def get_csv_columns() -> str:
    """
    This function returns the columns' name for the CSV file based on the loaded descriptors
    :return: A string line containing the columns' name for the CSV file
    """
    if settings.csv_header != "":
        return settings.csv_header
    descriptors_name: list[str] = [
        str(descriptor["name"]).replace(" ", "_").lower() for descriptor in settings.descriptors]
    columns: str = "src_file,contract_name"
    for name in sorted(descriptors_name):
        columns += f",{name}"
    settings.csv_header = columns
    return columns
