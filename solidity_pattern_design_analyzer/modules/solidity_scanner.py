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
                logging.debug("{} '{}'".format(colored("Parsing solidity source code file:", "blue"),
                                               colored(solidity_file_path, "cyan")))
            self._visitor = parser.objectify(
                parser.parse_file(solidity_file_path, loc=False))  # ObjectifySourceUnitVisitor
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
            logging.warning("{} '{}'\t{} '{}'".format(
                colored("Compatible Version:", "magenta"),
                colored(settings.solidity_version, "cyan"),
                colored("Loaded Version:", "magenta"),
                colored(loaded_version, "cyan")
            ))
            logging.warning(colored("The provided solidity source code file's version is not compatible.", "magenta"))
            user_confirm: bool = ask_confirm("Proceed anyway?")
            if not user_confirm:
                logging.info(colored("Aborting...", "yellow"))
            return user_confirm
        return True

    def _build_return_statement_string(self, statement_node: dict) -> str:
        """
        This function recursively inspects a return statement to string it
        :param statement_node: The statement node to analyze
        :return: A stringed return statement
        """
        return f"return {self._build_node_string(statement_node['expression'])}"

    def _build_emit_statement_string(self, statement_node: dict) -> str:
        """
        This function recursively inspects an emit statement to string it
        :param statement_node: The statement node to analyze
        :return: A stringed emit statement
        """
        return f"emit {self._build_node_string(statement_node['eventCall'])}"

    def _build_expression_statement_string(self, statement_node: dict) -> str:
        """
        This function recursively inspects an expression statement to string it
        :param statement_node: The statement node to analyze
        :return: A stringed expression statement
        """
        return self._build_node_string(statement_node['expression'])

    def _build_function_call_string(self, call_node: dict) -> str:
        """
        This function recursively inspects a function call to string it
        :param call_node: The call node to analyze
        :return: A stringed function call
        """
        expression_node: dict = call_node['expression']
        function_name: str = expression_node['name'] if "name" in expression_node else self._build_node_string(expression_node["expression"])
        function_call: str = f"{function_name}("
        arguments: list[dict] = call_node['arguments']
        for index, argument in enumerate(arguments):
            function_call += f"{self._build_node_string(argument)}"
            if index < len(arguments) - 1:
                function_call += ", "
        function_call += ")"
        return function_call

    def _build_binary_operation_string(self, operation_node: dict) -> str:
        """
        This function recursively inspects a binary operation to string it
        :param operation_node: The binary operation node to analyze
        :return: A stringed binary operation
        """
        return f"{self._build_node_string(operation_node['left'])} {operation_node['operator']} {self._build_node_string(operation_node['right'])}"

    def _build_variable_declaration_statement_string(self, declaration_node: dict) -> str:
        """
        This function recursively inspects a variable declaration to string it
        :param declaration_node: The variable declaration node to analyze
        :return: A stringed variable declaration
        """
        variables: list[dict] = declaration_node["variables"]
        declaration_text: str = "(" if len(variables) > 1 else ""
        for index, variable in enumerate(variables):
            declaration_text += f"{variable['name']}"
            if index < len(variables) - 1:
                declaration_text += ", "
        declaration_text += ")" if len(variables) > 1 else ""
        return f"{declaration_text} = {self._build_node_string(declaration_node['initialValue'])}"

    def _build_if_statement_string(self, if_statement_node: dict) -> str:
        """
        This function recursively inspects an if statement to string it
        :param if_statement_node: The if statement node to analyze
        :return: A stringed if statement
        """
        condition_text: str = self._build_node_string(if_statement_node["condition"])
        statement_body: str = self._build_node_string(if_statement_node["TrueBody"])
        return f"if {condition_text} {{{statement_body}}}"

    def _build_node_string(self, node: dict) -> str:
        """
        This function recursively inspects a node to string it
        :param node: The node to analyze
        :return: A stringed node
        """
        expression_type: str = node["type"] if "type" in node else ""
        match expression_type:
            case "ReturnStatement":
                return self._build_return_statement_string(node)
            case "EmitStatement":
                return self._build_emit_statement_string(node)
            case "ExpressionStatement":
                return self._build_expression_statement_string(node)
            case "FunctionCall":
                return self._build_function_call_string(node)
            case "BinaryOperation":
                return self._build_binary_operation_string(node)
            case "MemberAccess" | "NumberLiteral" | "stringLiteral" | "Identifier":
                return self._get_binary_operation_operand(node)
            case "VariableDeclarationStatement":
                return self._build_variable_declaration_statement_string(node)
            case "IfStatement":
                return self._build_if_statement_string(node)
            case _:
                logging.error(colored("Unable to decode the statement!", "red"))
                return ""

    def _find_literal(self, search_for: list[str], search_in: list[str]) -> bool:
        """
        This function checks if one of the provided item is a sub string or an item of a provided collection
        :param search_for: The list of items to find
        :param search_in: The list of items to search on
        :return: True if there is a match, False otherwise
        """
        for pattern_str in filter(lambda d: "*" in d, search_for):
            if settings.verbose:
                logging.debug("{} '{}'".format(colored("Found descriptor's literal pattern:", "magenta"),
                                               colored(pattern_str, "cyan")))
            for smart_contract_item in search_in:
                if settings.verbose:
                    logging.debug("\t{} '{}'".format(colored("Comparing literal pattern with", "magenta"),
                                                     colored(smart_contract_item, "cyan")))
                if pattern_str.replace("*", "") in smart_contract_item:
                    return True
        for item in filter(lambda d: "*" not in d, search_for):
            if settings.verbose:
                logging.debug("{} '{}' {}".format(
                    colored("Found descriptor's literal: ", "magenta"),
                    colored(item, "cyan"),
                    colored(", checking if it is used", "magenta")))
            if item in search_in:
                return True
        return False

    def _find_usage_of(self, function_name: str, function_args: list[str], statements: list[dict]) -> bool:
        """
        This function look for a function call of the provided function
        :param function_name:
        :param function_args:
        :param statements:
        :return:
        """
        function_expression: str = f"{function_name}("
        for index, argument in enumerate(function_args):
            function_expression += f"{argument}"
            if index != 0 and index < len(function_args) - 1:
                function_expression += ", "
        function_expression += ")"
        for statement in statements:
            statement_expression: str = self._build_node_string(statement)
            if "*" not in function_args:
                if function_expression in statement_expression:
                    return True
            elif f"{function_name}(" in statement_expression:
                return True
        return False

    def _get_base_contracts_name(self, smart_contract_name: str) -> list[str]:
        """
        This function returns the first-level parent (inheritance) of a specified smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A list of smart-contracts name
        """
        parents: list[str] = list()
        for smart_contract_parent in self._visitor.contracts[smart_contract_name]._node.baseContracts:
            parents.append(smart_contract_parent.baseName.namePath)
        return parents

    def _get_modifiers_name(self, smart_contract_name: str) -> list[str]:
        """
        This function returns the modifiers name defined or used in the specified smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A list of modifiers name
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        smart_contract_modifiers: list[str] = list(smart_contract_node.modifiers.keys())
        for function in smart_contract_node.functions:
            for modifier in smart_contract_node.functions[function]._node.modifiers:
                smart_contract_modifiers.append(modifier.name)
        return smart_contract_modifiers

    def _filter_statements_by_type(self, statements: list[dict], type_filter: str) -> list[dict]:
        return None

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
        for statement in statements:
            print(colored("Found statement:", "red"))
            pprint.pprint(statement)
            print("{} {}".format(colored("Rebuilt string:", "green"), colored(self._build_node_string(statement), "yellow")))
        return statements

    def _get_data_type_size(self, data_type_name: str) -> int:
        """
        This function returns the byte-size of a specified solidity data type
        :param data_type_name: The data type name
        :return: A integer corresponding to the data type's byte size
        """
        match data_type_name:
            case "address":
                return 20
            case "string":
                return 32
            case "integer" if "int" in data_type_name:
                int_size: str = data_type_name.replace("u", "").replace("int", "")
                return 32 if int_size == "" else int(int_size) / 8
            case "byte" if "byte" in data_type_name:
                byte_size: str = data_type_name.replace("s", "").replace("byte", "")
                return 1 if byte_size == "" else int(byte_size)
            case _:  # bool
                return 1

    def _get_binary_operation_operand(self, wrapped_operand: dict) -> str:
        """
        This function unwraps a condition operand and returns the string literal
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
                return self._build_function_call_string(wrapped_operand)
            case "Identifier":
                return wrapped_operand["name"]
            case "NumberLiteral":
                return str(wrapped_operand["number"])
            case "stringLiteral":
                return wrapped_operand["value"]
            case _:
                return ""

    def _get_comparison_reverse_operator(self, operator: str) -> str:
        """
        This function returns the logical reversed operator
        :param operator: An operation operator
        :return: The reserved operator
        """
        match operator:
            case ">":
                return "<"
            case ">":
                return ">"
            case "<=":
                return ">="
            case ">=":
                return "<="
            case _:  # "=="
                return "=="

    def _test_comparison_check(self, smart_contract_name: str, operator: str, operand_1: str, operand_2: str) -> bool:
        """
        This function executes the comparison check: it looks for comparison between the two provided
        operands
        :param smart_contract_name: The name of the smart contract to analyze
        :param operand_1: A equality comparison operand
        :param operand_2: A equality comparison operand
        :return: True if the comparison check is valid, False otherwise
        """
        binary_operation_node: list[dict] = self._filter_statements_by_type(
            statements=self._get_statements(smart_contract_name=smart_contract_name), type_filter="BinaryOperation")
        operand_1 = operand_1.lower()
        operand_2 = operand_2.lower()
        operators: list[str] = [operator, self._get_comparison_reverse_operator(operator)]
        smart_contract_equality_operands: list[tuple] = list()
        for statement in binary_operation_node:
            if statement["type"] == "IfStatement" or (
                    statement["type"] == "ReturnStatement" and "condition" in statement["expression"]):
                condition: dict = statement["condition"] if statement["type"] == "IfStatement" else \
                    statement["expression"]["condition"]
                if "operator" in condition and condition["operator"] in operators and condition[
                    "type"] == "BinaryOperation":
                    smart_contract_equality_operands.append((
                        self._get_binary_operation_operand(condition["right"]).lower(),
                        self._get_binary_operation_operand(condition["left"]).lower()))
            elif statement["type"] == "ExpressionStatement" and "arguments" in statement["expression"]:
                for argument in statement["expression"]["arguments"]:
                    if "operator" in argument and argument["operator"] in operators and \
                            argument["type"] == "BinaryOperation":
                        smart_contract_equality_operands.append((
                            self._get_binary_operation_operand(argument["left"]).lower(),
                            self._get_binary_operation_operand(argument["right"]).lower()))
        if not smart_contract_equality_operands:
            return False
        for (smart_contract_operand_1, smart_contract_operand_2) in smart_contract_equality_operands:
            match operator:
                case "==":
                    if (operand_1 in smart_contract_operand_1 and operand_2 in smart_contract_operand_2) \
                            or (operand_2 in smart_contract_operand_1 and operand_1 in smart_contract_operand_2):
                        return True
                case _:
                    if (operator == operators[0] and (
                            operand_1 in smart_contract_operand_1 and operand_2 in smart_contract_operand_2)) \
                            or (operator == operators[1] and (
                            operand_2 in smart_contract_operand_1 and operand_1 in smart_contract_operand_2)):
                        return True
        return False

    def _test_inheritance_check(self, smart_contract_name: str, parent_names: list[str]) -> bool:
        """
        This function executes the inheritance check: it looks for parents' name
        :param smart_contract_name: The name of the smart contract to analyze
        :param parent_names: A list of parents' name to look for
        :return: True if the inheritance check is valid, False otherwise
        """
        parents_names = list(map(lambda d: d.lower(), parent_names))
        smart_contract_parents: list[str] = list(
            map(lambda d: d.lower(), self._get_base_contracts_name(smart_contract_name=smart_contract_name)))
        return self._find_literal(search_for=parents_names, search_in=smart_contract_parents)

    def _test_modifier_check(self, smart_contract_name: str, modifiers: list[str]) -> bool:
        """
        This function executes the modifier check: it looks for definition and/or usage of the provided modifiers
        :param smart_contract_name: The name of the smart contract to analyze
        :param modifiers: A list of modifiers' name to look for
        :return: True if the modifier check is valid, False otherwise
        """
        modifiers: list[str] = list(map(lambda d: d.lower(), modifiers))
        smart_contract_modifiers: list[str] = list(
            set(map(lambda d: d.lower(), self._get_modifiers_name(smart_contract_name=smart_contract_name))))
        return self._find_literal(search_for=modifiers, search_in=smart_contract_modifiers)

    def _test_rejector_check(self, smart_contract_name) -> bool:
        """
        This function executes the rejector check: it looks if the contract implements only a rejection fallback
        :param smart_contract_name: The name of the smart contract to analyze
        :return: True if the rejector check is valid, False otherwise
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        smart_contract_functions: list[str] = list(smart_contract_node.functions.keys())
        if len(smart_contract_functions) == 1 \
                and smart_contract_functions[0] == "fallback" \
                and smart_contract_node.functions["fallback"].isFallback:
            return self._find_usage_of(function_name="revert", function_args=["*"],
                                       statements=smart_contract_node.functions["fallback"]._node.body.statements)
        return False

    def _test_tight_variable_packing_check(self, smart_contract_name) -> bool:
        """
        This function executes the tight_variable_packing check: it looks for a struct definition which size is <= 32 bytes
        :param smart_contract_name: The name of the smart contract to analyze
        :return: True if the tight_variable_packing check is valid, False otherwise
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        for struct_name in smart_contract_node.structs:
            if settings.verbose:
                logging.debug("{} '{}'".format(colored("Found struct:", "magenta"),
                                               colored(struct_name, "cyan")))
            struct_size: int = 0
            members: list[dict] = smart_contract_node.structs[struct_name]["members"]
            for member in members:
                if (member["typeName"]["type"] != "ElementaryTypeName") or ("fixed" in member["typeName"]["name"]):
                    struct_size = -1
                    break
                else:
                    struct_size += self._get_data_type_size(member["typeName"]["name"])
            if struct_size != -1 and struct_size <= 32:
                return True
        return False

    def _test_memory_array_building_check(self, smart_contract_name) -> bool:
        """
        This function executes the memory_array_building check: it looks a view function with returns a memory array
        :param smart_contract_name: The name of the smart contract to analyze
        :return: True if the memory_array_building check is valid, False otherwise
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        for function in smart_contract_node.functions:
            function_node: dict = smart_contract_node.functions[function]._node
            if function_node["stateMutability"] == "view":
                return_statements: dict = {}
                # pprint.pprint(return_statements)
                for statement in function_node["body"]["statements"]:
                    print("\n")
                    pprint.pprint(statement)
        return False

    def _execute_descriptor(self, smart_contract_name: str, descriptor_index: int) -> dict[str, bool]:
        """
        This function tests all the selected descriptor's checks
        :param smart_contract_name: The name of the smart contract to analyze
        :param descriptor_index: The index of the descriptor to execute
        :return: The validated status for each descriptor's checks
        """
        results: dict[str, bool] = {}
        descriptor: dict = self._descriptors[descriptor_index]
        if settings.verbose:
            logging.debug("{} '{}'".format(colored(f"Executing descriptor:", "blue"),
                                           colored(descriptor['name'], "cyan")))
        for check in descriptor["checks"]:
            check_type: str = check["check_type"]
            if settings.verbose:
                logging.debug("{} '{}'".format(colored(f"Testing check:", "blue"), colored(check_type, "cyan")))
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
                case "tight_variable_packing":
                    check_result = self._test_tight_variable_packing_check(smart_contract_name=smart_contract_name)
                case "memory_array_building":
                    check_result = self._test_memory_array_building_check(smart_contract_name=smart_contract_name)
                case _:
                    logging.error(colored(f"The check-type: '{check_type}' has not been implemented yet!", "red"))
            if settings.verbose:
                if check_result:
                    logging.debug(colored("Test passed!", "green"))
                else:
                    logging.debug(colored("Test failed!", "red"))
            results[check_type] = check_result
        return results

    def _find_design_pattern_usage(self, smart_contract_name: str) -> dict[str, dict[str, bool]]:
        """
        This function executes the provided descriptors against the selected smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A dictionary containing the usage statistics of each provided descriptor for the selected smart-contract
        """
        logging.info("{} '{}'".format(colored("Analyzing smart-contract: ", "yellow"),
                                      colored(smart_contract_name, "cyan")))
        results: dict[str, dict[str, bool]] = {}
        for (descriptor_index, descriptor_name) in enumerate(map(lambda d: d["name"], self._descriptors)):
            results[descriptor_name] = self._execute_descriptor(smart_contract_name=smart_contract_name,
                                                                descriptor_index=descriptor_index)
        return results

    def get_design_pattern_statistics(self) -> dict[str, dict[str, dict[str, bool]]]:
        """
        This function looks for design pattern usages in each provided smart-contract and return a statistic based on
        provided descriptors' checks
        :return: A dictionary containing the statistics for each provided smart-contract
        """
        results: dict[str, dict[str, dict[str, bool]]] = {}
        for smart_contract_name in self._visitor.contracts.keys():
            results[smart_contract_name] = self._find_design_pattern_usage(smart_contract_name=smart_contract_name)
        return results
