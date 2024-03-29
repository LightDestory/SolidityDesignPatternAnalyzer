import logging
from pathlib import Path

from colorama import init
from termcolor import colored

from modules.config import settings
from modules.descriptor_validator import DescriptorValidator
from modules.plotter import Plotter
from modules.solidity_scanner import SolidityScanner
from modules.utils.utils import bootstrap, terminal_result_formatter, save_analysis_results, ask_confirm, \
    save_describe_results, save_batch_analysis_results

logging.basicConfig(format='%(levelname)s:\t%(message)s', level=logging.DEBUG)
logging.getLogger("matplotlib").setLevel(logging.CRITICAL)
logging.getLogger("PIL.PngImagePlugin").setLevel(logging.CRITICAL)

scanner: SolidityScanner
batch_result_collector: dict[str, dict[str, dict[str, dict[str, dict[str, bool | str]]]]] = {}
execution_callable: callable


def execute_analysis(target_path: str) -> None:
    """
    Execute an analysis on the given solidity file
    :param target_path: The path of the solidity file to analyze
    :return: None
    """
    logging.info("%s '%s'", colored("Parsing solidity file: ", "yellow"), colored(target_path, "cyan"))
    if not scanner.parse_solidity_file(solidity_file_path=target_path):
        return
    logging.info(colored("Checking solidity version...", "yellow"))
    if not scanner.is_version_compatible():
        return
    try:
        if settings.execution_mode == "analyze":
            logging.info(colored("Searching for design patterns...", "yellow"))
            computation_results = scanner.get_design_pattern_statistics()
        else:
            logging.info(colored("Generating design pattern descriptors...", "yellow"))
            computation_results = scanner.generate_design_pattern_descriptors()
    except Exception as e:
        logging.error(colored(f"Execution interrupted by: {e}", "red"))
        return
    if not computation_results:
        logging.error(colored("The computation did not produce any results!, aborting...", "red"))
        return
    if settings.execution_mode == "analyze":
        if settings.batch_mode:
            batch_result_collector[target_path] = computation_results
        if settings.print_result:
            logging.info(terminal_result_formatter(computation_results))
        if settings.write_result == "always" or (settings.write_result == "ask" and ask_confirm(
                "Do you want to save the results to the disk?")):
            save_analysis_results(target_path, computation_results)
        if settings.plot == "always" or (settings.plot == "ask" and ask_confirm(
                "Do you want to create a results based plot?")):
            Plotter(computation_results).plot_results()
    else:
        save_describe_results(target_path, computation_results)


def execute_debug_analysis(target_path: str) -> None:
    """
    Execute a debug analysis on the given solidity file by exploring the AST and printing the findings
    :param target_path: The path of the solidity file to analyze
    :return: None
    """
    logging.info("%s '%s'", colored("Parsing solidity file: ", "green"), colored(target_path, "cyan"))
    if not scanner.parse_solidity_file(solidity_file_path=target_path):
        return
    scanner.debug_analysis()


def main() -> None:
    """
    Entry point of the program
    :return: None
    """
    global scanner, execution_callable
    execution_callable = execute_analysis
    current_dir: Path = Path(__file__).parent
    settings.schema_path = f"{current_dir}{settings.schema_path}"
    inputs: dict[str, str] = bootstrap(default_descriptor=Path(f"{current_dir}/descriptors/"))
    if settings.execution_mode == "debug":
        execution_callable = execute_debug_analysis
    if settings.execution_mode == "analyze":
        desc_validator = DescriptorValidator(inputs["descriptor"])
        logging.info(colored("Loading schema...", "yellow"))
        if not desc_validator.load_schema(schema_path=inputs["schema"]):
            exit(-1)
        logging.info(colored("Loading descriptors...", "yellow"))
        settings.descriptors = desc_validator.load_descriptors()
        if not settings.descriptors:
            exit(-1)
    scanner = SolidityScanner()
    try:
        if not settings.batch_mode:
            execution_callable(target_path=inputs["target"])
        else:
            target_directory: Path = Path(inputs["target"])
            for target_file in sorted(target_directory.glob('**/*.sol'), key=lambda x: len(x.name)):
                execution_callable(target_path=str(target_file))
            if settings.execution_mode == "analyze":
                save_batch_analysis_results(batch_result_collector, target_directory)
    except KeyboardInterrupt:
        logging.info(colored("Execution interrupted by the user!", "red"))
    finally:
        logging.info(colored("Job done!", "yellow"))


if __name__ == '__main__':
    init()
    main()
