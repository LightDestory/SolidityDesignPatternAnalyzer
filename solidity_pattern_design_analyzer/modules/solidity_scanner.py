import logging
import pprint

from termcolor import colored

from modules.solidity_parser import parser
from modules.config import settings
from modules.utils.utils import ask_confirm


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
                logging.debug(colored(f"Parsing solidity source code file: '{solidity_file_path}' ...", "blue"))
            self._visitor = parser.objectify(
                parser.parse_file(solidity_file_path, loc=True))  # ObjectifySourceUnitVisitor
        except Exception as ex:
            logging.error(
                colored(f"An unhandled error occurred while trying to parse the solidity file '{solidity_file_path}', "
                        f"aborting...\n{ex}", "red"))
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
            logging.warning(
                colored(f"Loaded Version: '{loaded_version}'\tCompatible Version: '{settings.solidity_version}'"
                        , "magenta"))
            logging.warning(colored("The provided solidity source code file's version is not compatible.", "magenta"))
            user_confirm: bool = ask_confirm("Proceed anyway?")
            if not user_confirm:
                logging.info(colored("Aborting...", "yellow"))
            return user_confirm
        return True

    def _get_statements(self, smart_contract_name: str) -> list[dict]:
        """
        This function retrieves all the statements of a specific smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A list of all the first-level statements
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        functions_statements: list[list[dict]] = [fun._node.body.statements for fun in
                                                  smart_contract_node.functions.values()]
        modifiers_statements: list[list[dict]] = [mod._node.body.statements for mod in
                                                  smart_contract_node.modifiers.values()]
        statements: list[dict] = [statement for fun_stats in functions_statements for statement in fun_stats]
        statements += [statement for mod_stats in modifiers_statements for statement in mod_stats]
        return statements

    def _get_operand(self, wrapped_operand: dict) -> str:
        """
        This functions unwraps a condition operand and returns the string literal
        :param wrapped_operand: The operand object of a condition
        :return: The operand string literal
        """
        operand_type: str = wrapped_operand["type"] if wrapped_operand["type"] else "Identifier"
        match operand_type:
            case "MemberAccess":
                name: str = f"{wrapped_operand['expression']['name']}." if "name" in wrapped_operand['expression'] \
                    else ""
                return f"{name}{wrapped_operand['memberName']}"
            case "FunctionCall":
                return wrapped_operand["expression"]["name"]
            case "Identifier":
                return wrapped_operand["name"]
            case _:
                return ""

    def _test_comparison_check(self, smart_contract_name: str, operator: str, operand_1: str, operand_2: str) -> bool:
        """
        This function executes the comparison check: it looks for comparison between the two provided
        operands
        :param smart_contract_name: The name of the smart contract to analyze
        :param operand_1: A equality comparison operand
        :param operand_2: A equality comparison operand
        :return: True if the comparison check is valid, False otherwise
        """
        statements: list[dict] = self._get_statements(smart_contract_name=smart_contract_name)
        operand_1 = operand_1.lower()
        operand_2 = operand_2.lower()
        smart_contract_equality_operands: list[tuple] = list()
        for statement in statements:
            print("\n")
            pprint.pprint(statement)
            if statement["type"] == "IfStatement" or (statement["type"] == "ReturnStatement" and "condition" in statement["expression"]):
                condition: dict = statement["condition"]  if  statement["type"] == "IfStatement" else statement["expression"]["condition"]
                if "operator" in condition and condition["operator"] == operator and condition["type"] == "BinaryOperation":
                    smart_contract_equality_operands.append((
                        self._get_operand(condition["right"]).lower(),
                        self._get_operand(condition["left"]).lower()))
            elif statement["type"] == "ExpressionStatement" and "arguments" in statement["expression"]:
                for argument in statement["expression"]["arguments"]:
                    if "operator" in argument and argument["operator"] == operator and \
                            argument["type"] == "BinaryOperation":
                        smart_contract_equality_operands.append((
                            self._get_operand(argument["left"]).lower(),
                            self._get_operand(argument["right"]).lower()))
        if not smart_contract_equality_operands:
            return False
        for (smart_contract_operand_1, smart_contract_operand_2) in smart_contract_equality_operands:
            match operator:
                case "==":
                    if (operand_1 in smart_contract_operand_1 and operand_2 in smart_contract_operand_2) \
                            or (operand_2 in smart_contract_operand_1 and operand_1 in smart_contract_operand_2):
                        return True
                case "<=" | ">=":
                    if operand_1 in smart_contract_operand_1 and operand_2 in smart_contract_operand_2:
                        return True
                case _:
                    return False
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
                if modifier.replace("*", "") in smart_contract_modifier:
                    return True
        for modifier in filter(lambda d: "*" not in d, modifiers):
            if modifier in smart_contract_modifiers:
                return True
        return False

    def _test_rejector_check(self, smart_contract_name) -> bool:
        """
        This function executes the rejector check: it looks if the contract implements only a rejection fallback
        :param smart_contract_name: The name of the smart contract to analyze
        :return: True if the rejector check is valid, False otherwise
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        smart_contract_functions: list[str] = list(smart_contract_node.functions.keys())
        if len(smart_contract_functions) == 1 \
                and smart_contract_functions[0] == "fallback"\
                and smart_contract_node.functions["fallback"].isFallback:
            for statement in smart_contract_node.functions["fallback"]._node.body.statements:
                if statement["type"] == "ExpressionStatement":
                    if self._get_operand(statement["expression"]) == "revert":
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
            logging.debug(colored(f"Executing descriptor: '{descriptor['name']}' ...", "blue"))
        for check in descriptor["checks"]:
            check_type: str = check["check_type"]
            if settings.verbose:
                logging.debug(colored(f"Testing check: '{check_type}' ...", "blue"))
            check_result: bool = False
            match check_type:
                case "inheritance":
                    check_result = self._test_inheritance_check(smart_contract_name=smart_contract_name,
                                                                parent_names=check["parent_names"])
                case "modifier":
                    check_result = self._test_modifier_check(smart_contract_name=smart_contract_name,
                                                             modifiers=check["modifiers"])
                case "comparison":
                    check_result = self._test_comparison_check(smart_contract_name=smart_contract_name,
                                                               operator=check["operator"],
                                                               operand_1=check["operand_1"],
                                                               operand_2=check["operand_2"])
                case "rejector":
                    check_result = self._test_rejector_check(smart_contract_name=smart_contract_name)
                case _:
                    logging.error(colored(f"The check-type: '{check_type}' has not been implemented yet!", "red"))
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
        logging.info(colored(f"Analyzing smart-contract: '{smart_contract_name}' ...", "cyan"))
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
