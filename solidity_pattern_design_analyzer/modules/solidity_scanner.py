import logging
import pprint

from termcolor import colored

from modules.solidity_parser import parser
from modules.config import settings


class SolidityScanner:
    _visitor = None  # ObjectifySourceUnitVisitor
    _descriptors: list[dict]

    def __init__(self, descriptors: list[dict]):
        self._descriptors = descriptors

    def parse_solidity_file(self, solidity_file_path: str) -> bool:
        """
        This function parses the solidity source code file provided and stores a visitor
        :param solidity_file_path: A valid solidity source code file path
        :return: True if parsed successfully, False otherwise
        """
        try:
            if settings.verbose:
                logging.debug(colored("Parsing solidity source code file: '{}' ...".format(solidity_file_path), "blue"))
            self._visitor = parser.objectify(
                parser.parse_file(solidity_file_path))  # ObjectifySourceUnitVisitor
        except Exception as ex:
            logging.error(colored("An unhandled error occurred while trying to parse the solidity file '{}', "
                                  "aborting...\n{}".format(solidity_file_path, ex), "red"))
            return False
        if settings.verbose:
            logging.debug(colored("Solidity source code parsed successfully!", "green"))
        return True

    def is_version_compatible(self) -> bool:
        """
        This functions reads the solidity pragma to check the used solidity version
        :return: True if the version is compatible or by user's decision, False otherwise
        """
        loaded_version: str = "Unknown"
        for pragma in self._visitor.pragmas:
            if pragma["name"] == "solidity":
                loaded_version = pragma["value"]
        if loaded_version != settings.solidity_version and not settings.allow_incompatible:
            logging.warning(colored("Loaded Version: '{}'\tCompatible Version: '{}'"
                                    .format(loaded_version, settings.solidity_version), "magenta"))
            logging.warning(colored("The provided solidity source code file's version is not compatible.", "magenta"))
            while True:
                try:
                    answer: str = input(colored("Proceed anyway? [y/n]: ", "magenta")).lower()
                    if answer == "y" or answer == "n":
                        if answer == "y":
                            break
                        else:
                            logging.info(colored("Aborting...", "yellow"))
                            return False
                except KeyboardInterrupt:
                    print("\n")  # Fixes no new line after input's prompts
                    logging.info(colored("KeyboardInterrupt intercepted, aborting...", "yellow"))
                    return False
        return True

    def _get_condition_operand(self, wrapped_operand: dict) -> str:
        """
        This functions unwraps a condition operand and returns the string literal
        :param wrapped_operand: The operand object of a condition
        :return: The operand string literal
        """
        operand_type: str = wrapped_operand["type"] if wrapped_operand["type"] else "Identifier"
        match operand_type:
            case "MemberAccess":
                return "{}.{}".format(wrapped_operand["expression"]["name"], wrapped_operand["memberName"])
            case "FunctionCall":
                return wrapped_operand["expression"]["name"]
            case "Identifier":
                return wrapped_operand["name"]
            case _:
                return ""

    def _test_equality_condition_check(self, smart_contract_name: str, operand_1: str, operand_2: str) -> bool:
        """
        This function executes the equality_condition check: it looks for equality comparison between the two provided
        operands
        :param smart_contract_name: The name of the smart contract to analyze
        :param operand_1: A equality comparison operand
        :param operand_2: A equality comparison operand
        :return: True if the equality_condition check is valid, False otherwise
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        operand_1 = operand_1.lower()
        operand_2 = operand_2.lower()
        for function in smart_contract_node.functions:
            for statement in smart_contract_node.functions[function]._node.body.statements:
                if statement["type"] == "IfStatement" and statement["condition"]["operator"] == "==" \
                        and statement["condition"]["type"] == "BinaryOperation":
                    smart_contract_operand_1: str = self._get_condition_operand(statement["condition"]["right"]).lower()
                    smart_contract_operand_2: str = self._get_condition_operand(statement["condition"]["left"]).lower()
                    if not smart_contract_operand_1 or not smart_contract_operand_2:
                        return False
                    if (smart_contract_operand_1 == operand_1 and smart_contract_operand_2 == operand_2) \
                            or (smart_contract_operand_1 == operand_2 and smart_contract_operand_2 == operand_1):
                        return True
        return False

    def _test_inheritance_check(self, smart_contract_name: str, parent_names: list[str]) -> bool:
        """
        This function executes the inheritance check: it looks for parents' name
        :param smart_contract_name: The name of the smart contract to analyze
        :param parent_names: A list of parents' name to look for
        :return: True if the inheritance check is valid, False otherwise
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        parents_name = list(map(lambda d: d.lower(), parent_names))
        for smart_contract_parent in smart_contract_node._node.baseContracts:
            if smart_contract_parent.baseName.namePath.lower() in parents_name:
                return True
        return False

    def _test_modifier_check(self, smart_contract_name: str, modifiers: list[str]) -> bool:
        """
        This function executes the modifier check: it looks for definition and/or usage of the provided modifiers
        :param smart_contract_name: The name of the smart contract to analyze
        :param modifiers: A list of modifiers' name to look for
        :return: True if the modifier check is valid, False otherwise
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        modifiers = list(map(lambda d: d.lower(), modifiers))
        smart_contract_modifiers: set[str] = set(map(lambda d: d.lower(), smart_contract_node.modifiers.keys()))
        for function in smart_contract_node.functions:
            for modifier in smart_contract_node.functions[function]._node.modifiers:
                smart_contract_modifiers.add(modifier.name.lower())
        for modifier in filter(lambda d: "*" in d, modifiers):
            for smart_contract_modifier in smart_contract_modifiers:
                if str.replace("*", "", modifier) in smart_contract_modifier:
                    return True
        for modifier in filter(lambda d: "*" not in d, modifiers):
            if modifier in smart_contract_modifiers:
                return True
        return False

    def _execute_descriptor(self, smart_contract_name: str, descriptor_index: int) -> int:
        """
        This function tests all the selected descriptor's checks
        :param smart_contract_name: The name of the smart contract to analyze
        :param descriptor_index: The index of the descriptor to execute
        :return: The number of descriptor's passed checks
        """
        validated_checks: int = 0
        descriptor: dict = self._descriptors[descriptor_index]
        if settings.verbose:
            logging.debug(colored("Executing descriptor: '{}' ...".format(descriptor["name"]), "blue"))
        for check in descriptor["checks"]:
            check_type: str = check["check_type"]
            if settings.verbose:
                logging.debug(colored("Testing check: '{}' ...".format(check_type), "blue"))
            check_result: bool = False
            match check_type:
                case "inheritance":
                    check_result = self._test_inheritance_check(smart_contract_name=smart_contract_name,
                                                                parent_names=check["parent_names"])
                case "modifier":
                    check_result = self._test_modifier_check(smart_contract_name=smart_contract_name,
                                                             modifiers=check["modifiers"])
                case "equality_condition":
                    check_result = self._test_equality_condition_check(smart_contract_name=smart_contract_name,
                                                                       operand_1=check["operand_1"],
                                                                       operand_2=check["operand_2"])
                case _:
                    logging.error(colored("The check-type: '{}' has not been implemented yet!".format(check_type),
                                          "red"))
            if settings.verbose:
                if check_result:
                    logging.debug(colored("Test passed!", "green"))
                else:
                    logging.debug(colored("Test failed!", "red"))
            validated_checks += int(check_result)
        return validated_checks

    def _find_design_pattern_usage(self, smart_contract_name: str) -> dict[str, int]:
        """
        This function executes the provided descriptors against the selected smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A dictionary containing the usage statistics of each provided descriptor for the selected smart-contract
        """
        logging.info(colored("Analyzing smart-contract: '{}' ...".format(smart_contract_name), "cyan"))
        results: dict[str, int] = {}
        for (descriptor_index, descriptor_name) in enumerate(map(lambda d: d["name"], self._descriptors)):
            results[descriptor_name] = self._execute_descriptor(smart_contract_name=smart_contract_name,
                                                                descriptor_index=descriptor_index)
        return results

    def get_design_pattern_statistics(self) -> dict[str, dict[str, int]]:
        """
        This function looks for design pattern usages in each provided smart-contract and return a statistic based on
        provided descriptors' checks :return: A dictionary containing the statistics for each provided smart-contract
        """
        results: dict[str, dict[str, int]] = {}
        for smart_contract_name in self._visitor.contracts.keys():
            results[smart_contract_name] = self._find_design_pattern_usage(smart_contract_name=smart_contract_name)
        return results

