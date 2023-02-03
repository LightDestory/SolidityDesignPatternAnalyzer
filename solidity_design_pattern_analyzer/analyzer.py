import logging
from pathlib import Path

from colorama import init
from termcolor import colored

from modules.config import settings
from modules.descriptor_validator import DescriptorValidator
from modules.plotter import Plotter
from modules.solidity_scanner import SolidityScanner
from modules.utils.utils import bootstrap, format_analysis_results, save_analysis_results, ask_confirm, \
    save_describe_results

logging.basicConfig(format='%(levelname)s:\t%(message)s', level=logging.DEBUG)
logging.getLogger("matplotlib").setLevel(logging.CRITICAL)
logging.getLogger("PIL.PngImagePlugin").setLevel(logging.CRITICAL)


def main() -> None:
    current_dir: Path = Path(__file__).parent
    settings.schema_path = f"{current_dir}{settings.schema_path}"
    inputs: dict[str, str] = bootstrap(default_descriptor=Path(f"{current_dir}/descriptors/"))
    desc_validator = DescriptorValidator(inputs["descriptor"])
    computation_results: dict[str, dict[str, dict[str, bool]]] | dict[str, list[dict]]
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
        computation_results = scanner.get_design_pattern_statistics()
    else:
        logging.info(colored("Generating design pattern descriptors...", "yellow"))
        computation_results = scanner.generate_design_pattern_descriptors()
    if not computation_results:
        logging.error(colored("The computation did not produce any results!, aborting...", "red"))
        exit(-1)
    if inputs["action"] == "analyze":
        logging.info(format_analysis_results(computation_results))
        save_analysis_results(inputs["target"], computation_results)
        if settings.auto_plot or ask_confirm("Do you want to create a results based plot?"):
            Plotter(computation_results).plot_results()
    else:
        save_describe_results(inputs["target"], computation_results)
    logging.info(colored("Job done!", "yellow"))


if __name__ == '__main__':
    init()
    main()
