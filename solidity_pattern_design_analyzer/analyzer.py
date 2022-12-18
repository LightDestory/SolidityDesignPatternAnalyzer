import logging
from pathlib import Path

from colorama import init
from termcolor import colored

from modules.config import settings
from modules.descriptor_validator import DescriptorValidator
from modules.plotter import Plotter
from modules.solidity_scanner import SolidityScanner
from modules.utils.utils import bootstrap, format_results, save_results, ask_confirm

logging.basicConfig(format='%(levelname)s:\t%(message)s', level=logging.DEBUG)
logging.getLogger("matplotlib").setLevel(logging.CRITICAL)
logging.getLogger("PIL.PngImagePlugin").setLevel(logging.CRITICAL)


def main() -> None:
    inputs: dict[str, str] = bootstrap(default_schema=Path("./modules/data/descriptor_schema.json"),
                                       default_descriptor=Path("./descriptors/"))
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
    if inputs["action"] == "analyze":
        logging.info(colored("Searching for design patterns...", "yellow"))
        analysis_results: dict[str, dict[str, dict[str, bool]]] = scanner.get_design_pattern_statistics()
        if not analysis_results:
            logging.error(colored("No smart-contract found!, aborting...", "red"))
            exit(-1)
        logging.info(format_results(analysis_results))
        save_results(inputs["target"], analysis_results)
        if settings.auto_plot or ask_confirm("Do you want to create a results based plot?"):
            Plotter(analysis_results).plot_results()
    logging.info(colored("Job done!", "yellow"))


if __name__ == '__main__':
    init()
    main()
