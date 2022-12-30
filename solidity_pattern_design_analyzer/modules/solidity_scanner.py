import logging
import pprint

from termcolor import colored

from modules.solidity_parser import parser
from modules.config import settings
from modules.utils.utils import ask_confirm


class SolidityScanner:
    _visitor = None  # ObjectifySourceUnitVisitor
    _descriptors: list[dict]
    _statements_collector: dict[str, dict[str, dict[str, list[dict]]]] = {}
    _implemented_tests: list[str]
    _generic_tests: list[str] = [
        "comparison", "inheritance", "modifier", "fn_return_parameters", "fn_call", "fn_definition", "event_emit",
        "enum_definition", "state_toggle"
    ]
    _specialized_tests: list[str] = [
        "rejector", "tight_variable_packing", "memory_array_building", "check_effects_interaction"
    ]
    _statement_operand_types: list[str] = [
        "MemberAccess", "NumberLiteral", "stringLiteral", "Identifier", "ElementaryTypeName", "ArrayTypeName",
        "BooleanLiteral", "UserDefinedTypeName", "HexLiteral", "IndexAccess"
    ]
    _reverse_comparison_operand_map: dict[str, str] = {
        ">": "<",
        "<": ">",
        "<=": ">=",
        ">=": "<=",
        "==": "=="
    }
    _assignment_operands: list[str] = ["=", "+=", "-="]
    _fixed_data_type_byte_sizes: dict[str, int] = {
        "address": 20,
        "string": 32,
        "bool": 1
    }

    def __init__(self, descriptors: list[dict]):
        self._descriptors = descriptors
        self._implemented_tests = self._generic_tests + self._specialized_tests

    def parse_solidity_file(self, solidity_file_path: str) -> bool:
        """
        This function parses the solidity source code file provided and stores a visitor
        :param solidity_file_path: A valid solidity source code file path
        :return: True if parsed successfully, False otherwise
        """
        try:
            if settings.verbose:
                logging.debug("%s '%s'", colored("Parsing solidity source code file:", "blue"),
                              colored(solidity_file_path, "cyan"))
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
            logging.warning("%s '%s'\t%s '%s'",
                            colored("Compatible Version:", "magenta"),
                            colored(settings.solidity_version, "cyan"),
                            colored("Loaded Version:", "magenta"),
                            colored(loaded_version, "cyan")
                            )
            logging.warning(colored("The provided solidity source code file's version is not compatible.", "magenta"))
            user_confirm: bool = ask_confirm("Proceed anyway?")
            if not user_confirm:
                logging.info(colored("Aborting...", "yellow"))
            return user_confirm
        return True

    def _collect_statements(self, smart_contract_name: str) -> None:
        """
        Collects the functions and modifiers of the selected contract
        :param smart_contract_name: The name of the smart contract to analyze
        """
        if settings.verbose:
            logging.debug(colored(f"Collecting statements...", "magenta"))
        self._statements_collector[smart_contract_name] = {"functions": {}, "modifiers": {}}
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        for fn_name in smart_contract_node.functions:
            self._statements_collector[smart_contract_name]["functions"][fn_name] = \
                smart_contract_node.functions[fn_name]._node.body.statements
        for modifier_name in smart_contract_node.modifiers:
            self._statements_collector[smart_contract_name]["modifiers"][modifier_name] = \
                smart_contract_node.modifiers[modifier_name]._node.body.statements
        if settings.verbose:
            for item_type in ["functions", "modifiers"]:
                for name, statements in self._statements_collector[smart_contract_name][item_type].items():
                    logging.debug("%s %s", colored(f"Rebuilding {item_type}:", "magenta"), colored(name, "cyan"))
                    for statement in statements:
                        result: str = self._build_node_string(statement)
                        if "UDST_Error" in result:
                            pprint.pprint(statement)
                            exit(-1)
                        logging.debug(
                            "\t%s %s", colored("Rebuilt statement:", "magenta"), colored(result, "cyan"))

    def _compare_return_parameters(self, fn_return_parameters: list[dict], provided_parameters: list[dict]) -> bool:
        """
        This function checks if a set of parameters is returned by the provided function
        :param fn_return_parameters: The returnParameters node of a function to analyze
        :param provided_parameters: A set of return types
        :return: True if all parameters are found, False otherwise
        """
        if len(fn_return_parameters) >= len(provided_parameters):
            for provided_parameter in provided_parameters:
                for smart_contract_fn_parameter in fn_return_parameters:
                    if smart_contract_fn_parameter["type"] == provided_parameter["type"].lower():
                        provided_location: str = provided_parameter["storage_location"].lower()
                        if provided_location == "*" or \
                                (smart_contract_fn_parameter["storage_location"] == provided_location):
                            fn_return_parameters.remove(smart_contract_fn_parameter)
                            break
            if len(fn_return_parameters) == 0:
                return True
        return False

    def _compare_literal(self, search_for: set[str], search_in: set[str]) -> bool:
        """
        This function checks if one of the provided item is a sub string or an item of a provided collection
        :param search_for: The list of items to find
        :param search_in: The list of items to search on
        :return: True if there is a match, False otherwise
        """
        string_patters: list[str] = list(filter(lambda d: "*" in d, search_for))
        if string_patters:
            if settings.verbose:
                logging.debug("%s '%s'", colored("Checking descriptor's string patterns:", "magenta"),
                              colored(pprint.pformat(string_patters), "cyan"))
            for pattern_str in string_patters:
                for smart_contract_item in search_in:
                    if "*any*" in pattern_str:
                        pattern_str = pattern_str[:pattern_str.index("*any*")]
                    else:
                        pattern_str = pattern_str.replace("*", "")
                    if pattern_str in smart_contract_item:
                        return True
        string_literals: list[str] = list(filter(lambda d: "*" not in d, search_for))
        if string_literals:
            if settings.verbose:
                logging.debug("%s '%s'", colored("Checking descriptor's string literals:", "magenta"),
                              colored(pprint.pformat(string_literals), "cyan"))
            for item in string_literals:
                if item in search_in:
                    return True
        return False

    def _build_node_string(self, node: dict) -> str:
        """
        This function recursively inspects a node to string it
        :param node: The node to analyze
        :return: A stringed node
        """
        node_type: str = node["type"] if "type" in node else ""
        match node_type:
            case "ReturnStatement":
                return f"return {self._build_node_string(node['expression'])}"
            case "EmitStatement":
                return f"emit {self._build_node_string(node['eventCall'])}"
            case "ExpressionStatement":
                return self._build_node_string(node['expression'])
            case "FunctionCall":
                return self._build_function_call_string(node)
            case "UnaryOperation":
                if node["isPrefix"]:
                    return f"{node['operator']}{self._build_node_string(node['subExpression'])}"
                return f"{self._build_node_string(node['subExpression'])}{node['operator']}"
            case "BinaryOperation":
                return f"{self._build_node_string(node['left'])} {node['operator']} {self._build_node_string(node['right'])}"
            case node_type if node_type in self._statement_operand_types:
                return self._get_statement_operand(node)
            case "VariableDeclarationStatement":
                return self._build_variable_declaration_statement_string(node)
            case "IfStatement":
                return self._build_if_statement_string(node)
            case "WhileStatement" | "DoWhileStatement":
                return self._build_while_loop_string(node)
            case "ForStatement":
                return self._build_for_loop_string(node)
            case "NewExpression":
                return f"new {self._build_node_string(node['typeName'])}"
            case "Block":
                return f"{{{self._build_block_string(node)}}}"
            case "Conditional":
                return f"{self._build_node_string(node['condition'])} ? {self._build_node_string(node['TrueExpression'])} : {self._build_node_string(node['FalseExpression'])}"
            case "TupleExpression":
                return self._build_tuple_string(node)
            case _:
                logging.error(colored(f"Unable to decode the statement: {node_type}", "red"))
                return "UDST_Error"

    def _build_function_call_string(self, call_node: dict) -> str:
        """
        This function recursively inspects a function call to string it
        :param call_node: The call node to analyze
        :return: A stringed function call
        """
        function_name: str = call_node['name'] if "name" in call_node else self._build_node_string(
            call_node["expression"])
        function_call: str = f"{function_name}("
        arguments: list[dict] = call_node['arguments']
        for index, argument in enumerate(arguments):
            function_call += f"{self._build_node_string(argument)}"
            if index < len(arguments) - 1:
                function_call += ", "
        function_call += ")"
        return function_call

    def _build_variable_declaration_statement_string(self, declaration_node: dict) -> str:
        """
        This function recursively inspects a variable declaration to string it
        :param declaration_node: The variable declaration node to analyze
        :return: A stringed variable declaration
        """
        variables: list[dict] = declaration_node["variables"]
        declaration_text: str = "(" if len(variables) > 1 else ""
        initialization_text: str = ""
        for index, variable in enumerate(variables):
            if not variable:
                continue
            storage_location: str = f" {variable['storageLocation']} " if variable["storageLocation"] else " "
            declaration_text += f"{self._build_node_string(variable['typeName'])}{storage_location}{variable['name']}"
            if index < len(variables) - 1:
                declaration_text += ", "
        declaration_text += ")" if len(variables) > 1 else ""
        if declaration_node['initialValue']:
            initialization_text = f" = {self._build_node_string(declaration_node['initialValue'])}"
        return f"{declaration_text}{initialization_text}"

    def _build_if_statement_string(self, if_statement_node: dict) -> str:
        """
        This function recursively inspects an if statement to string it
        :param if_statement_node: The if statement node to analyze
        :return: A stringed if statement
        """
        condition_text: str = self._build_node_string(if_statement_node["condition"])
        true_body: str = self._build_node_string(if_statement_node["TrueBody"])
        false_body: str = ""
        if if_statement_node["FalseBody"]:
            false_body: str = f"else {self._build_node_string(if_statement_node['FalseBody'])}"
        return f"if {condition_text} {true_body} {false_body}"

    def _build_while_loop_string(self, while_node: dict) -> str:
        """
        This function recursively inspects a while/do while loop to string it
        :param while_node: The while/do while loop node to analyze
        :return: A stringed while/do while loop
        """
        loop_type: str = while_node["type"]
        condition_text: str = self._build_node_string(while_node["condition"])
        loop_body: str = self._build_node_string(while_node["body"])
        if loop_type == "WhileStatement":
            return f"while ({condition_text}) {loop_body}"
        else:
            return f"do {loop_body} while({condition_text})"

    def _build_for_loop_string(self, for_node: dict) -> str:
        """
        This function recursively inspects a for loop to string it
        :param for_node: The for node to analyze
        :return: A stringed for loop
        """
        init_condition: str = self._build_node_string(for_node["initExpression"])
        condition_expression: str = self._build_node_string(for_node["conditionExpression"])
        loop_expression: str = self._build_node_string(for_node["loopExpression"])
        return f"for({init_condition}; {condition_expression}; {loop_expression}) {self._build_node_string(for_node['body'])}"

    def _build_block_string(self, block_node: dict) -> str:
        """
        This function recursively inspects a block of statements to string it
        :param block_node: The block of statements to analyze
        :return: A stringed block of statements
        """
        statements: list[dict] = block_node["statements"]
        statements_text = ""
        for statement in statements:
            statements_text += f"{self._build_node_string(statement)}; "
        return statements_text

    def _build_tuple_string(self, tuple_node: dict) -> str:
        """
        This function recursively inspects a tuple expression to string it
        :param tuple_node: The tuple node to analyze
        :return: A stringed tuple
        """
        components: list[dict] = tuple_node["components"]
        declaration_text: str = "("
        for index, component in enumerate(components):
            declaration_text += f"{self._build_node_string(component)}"
            if index < len(components) - 1:
                declaration_text += ", "
        declaration_text += ")"
        return declaration_text

    def _get_all_bool_state_vars(self, smart_contract_name: str) -> set[str]:
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        return set([k.lower() for k, v in smart_contract_node.stateVars.items() if
                    v["typeName"]["name"] == "bool"])

    def _get_base_contract_names(self, smart_contract_name: str) -> set[str]:
        """
        This function returns the first-level parent names (inheritance) of a specified smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A set of smart-contract names
        """
        parents: set[str] = set()
        for smart_contract_parent in self._visitor.contracts[smart_contract_name]._node.baseContracts:
            parents.add(smart_contract_parent.baseName.namePath.lower())
        return parents

    def _get_modifier_names(self, smart_contract_name: str) -> set[str]:
        """
        This function returns the modifier names defined or used in the specified smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A set of modifier names
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        smart_contract_modifiers: set[str] = set(map(lambda d: d.lower(), smart_contract_node.modifiers.keys()))
        for function in smart_contract_node.functions:
            for modifier in smart_contract_node.functions[function]._node.modifiers:
                smart_contract_modifiers.add(modifier.name.lower())
        return smart_contract_modifiers

    def _get_fn_names(self, smart_contract_name: str) -> set[str]:
        """
        This function returns the function names defined in the specified smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A set of function names
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        return set(map(lambda d: smart_contract_node.functions[d]._node["name"].lower(),
                       smart_contract_node.functions))

    def _get_event_names(self, smart_contract_name: str) -> set[str]:
        """
        This function returns the event names defined in the specified smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A set of event names
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        return set(map(lambda d: smart_contract_node.events[d]._node["name"].lower(),
                       smart_contract_node.events))

    def _get_enum_names(self, smart_contract_name: str) -> set[str]:
        """
        This function returns the enum names defined in the specified smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A set of enum names
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        return set(map(lambda d: d.lower(), smart_contract_node.enums.keys()))

    def _get_fn_return_parameters(self, fn_node: dict) -> list[dict]:
        """
        This function returns all the return parameters of the specified smart-contract's function
        :param fn_node: A function node to analyze
        :return: A list of return parameters containing storage location and type
        """
        return_parameters: list[dict] = []
        for parameter in fn_node["returnParameters"]["parameters"]:
            data: dict = {
                "type": parameter["typeName"]["type"].lower(),
                "storage_location": "*"
            }
            if parameter["storageLocation"]:
                data["storage_location"] = parameter["storageLocation"].lower()
                return_parameters.append(data)
        return return_parameters

    def _get_all_fn_return_parameters(self, smart_contract_name: str) -> dict[str, list[dict]]:
        """
        This function returns all the return parameters of all the smart-contract's functions
        :param smart_contract_name:The name of the smart contract to analyze
        :return: A list of return parameters containing storage location and type for each smart-contract's function
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        return_parameters: dict[str, list[dict]] = {}
        for function in smart_contract_node.functions:
            function_node: dict = smart_contract_node.functions[function]._node
            if not function_node["returnParameters"]:
                continue
            parameters: list[dict] = self._get_fn_return_parameters(function_node)
            if parameters:
                return_parameters[function] = parameters
        return return_parameters

    def _get_all_statements(self, smart_contract_name: str, type_filter: str = "") -> list[dict]:
        """
        This function retrieves all the statements of a specific smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :param type_filter: A filter to et only specific statements
        :return: A list of all the first-level statements
        """
        statements_pool: list[dict] = []
        for item_type in ["functions", "modifiers"]:
            for name, statements in self._statements_collector[smart_contract_name][item_type].items():
                statements_pool += statements
        if not type_filter:
            return statements_pool
        else:
            filtered_statements: list[dict] = list()
            for statement in statements_pool:
                filtered: list[dict] = self._find_node_by_type(statement, type_filter)
                if filtered:
                    filtered_statements += filtered
            return filtered_statements

    def _get_all_comparison_statements(self, smart_contract_name: str) -> list[dict]:
        """
        This function returns all the Binary Operations that uses a comparison operator
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A list of comparison statements
        """
        return list(filter(lambda d: d["operator"] in self._reverse_comparison_operand_map.keys(),
                           self._get_all_statements(smart_contract_name=smart_contract_name,
                                                    type_filter="BinaryOperation")))

    def _get_all_assignment_statements(self, smart_contract_name: str) -> list[dict]:
        """
        This function returns all the Binary Operations that uses an assigment operator
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A list of assignment statements
        """
        return list(filter(lambda d: d["operator"] in self._assignment_operands,
                           self._get_all_statements(smart_contract_name=smart_contract_name,
                                                    type_filter="BinaryOperation")))

    def _get_data_type_byte_size(self, data_type_name: str) -> int:
        """
        This function returns the byte-size of a specified solidity data type
        :param data_type_name: The data type name
        :return: A integer corresponding to the data type's byte size
        """
        if data_type_name in self._fixed_data_type_byte_sizes.keys():
            return self._fixed_data_type_byte_sizes[data_type_name]
        elif "int" in data_type_name:
            int_size: str = data_type_name.replace("u", "").replace("int", "")
            return 32 if int_size == "" else int(int_size) // 8
        elif "byte" in data_type_name:
            byte_size: str = data_type_name.replace("s", "").replace("byte", "")
            return 1 if byte_size == "" else int(byte_size)
        raise Exception(f"Unsupported data type: {data_type_name}")

    def _get_statement_operand(self, wrapped_operand: dict) -> str:
        """
        This function unwraps a condition operand and returns the string literal
        :param wrapped_operand: The operand object of a condition
        :return: The operand string literal
        """
        operand_type: str = wrapped_operand["type"] if wrapped_operand["type"] else "Identifier"
        match operand_type:
            case "MemberAccess":
                return f"{self._build_node_string(wrapped_operand['expression'])}.{wrapped_operand['memberName']}"
            case "FunctionCall":
                return self._build_function_call_string(wrapped_operand)
            case "Identifier" | "ElementaryTypeName":
                return wrapped_operand["name"]
            case "NumberLiteral":
                value: str = str(wrapped_operand["number"])
                if wrapped_operand["subdenomination"]:
                    value += f" {wrapped_operand['subdenomination']}"
                return value
            case "stringLiteral" | "BooleanLiteral" | "HexLiteral":
                return f"\"{wrapped_operand['value']}\""
            case "ArrayTypeName":
                length: str = str(wrapped_operand["length"]) if wrapped_operand["length"] else ""
                return f"{self._build_node_string(wrapped_operand['baseTypeName'])}[{length}]"
            case "UserDefinedTypeName":
                return wrapped_operand["namePath"]
            case "IndexAccess":
                return f"{self._build_node_string(wrapped_operand['base'])}[{self._build_node_string(wrapped_operand['index'])}]"
            case _:
                raise Exception(f"Unsupported operand type: {operand_type}")

    def _find_node_by_type(self, node: dict, type_filter: str) -> list[dict]:
        """
        This function recursively inspects a node to find a specific sub-node
        :param node: The node to analyze
        :return: The note itself or None
        """
        if not node:
            return []
        node_type: str = node["type"] if "type" in node else ""
        if node_type == type_filter:
            return [node]
        else:
            match node_type:
                case "ReturnStatement":
                    return self._find_node_by_type(node["expression"], type_filter)
                case "EmitStatement":
                    return self._find_node_by_type(node["eventCall"], type_filter)
                case "ExpressionStatement":
                    return self._find_node_by_type(node["expression"], type_filter)
                case "FunctionCall":
                    arguments: dict = node["arguments"]
                    collector: list[dict] = list()
                    for argument in arguments:
                        collector += self._find_node_by_type(argument, type_filter)
                    return collector
                case "IfStatement":
                    return self._find_node_by_type(node["condition"], type_filter) + \
                        self._find_node_by_type(node["TrueBody"], type_filter) + \
                        self._find_node_by_type(node["FalseBody"], type_filter)
                case "WhileStatement" | "DoWhileStatement":
                    return self._find_node_by_type(node["condition"], type_filter) + \
                        self._find_node_by_type(node["body"], type_filter)
                case "ForStatement":
                    return self._find_node_by_type(node["initExpression"], type_filter) + \
                        self._find_node_by_type(node["conditionExpression"], type_filter) + \
                        self._find_node_by_type(node["loopExpression"], type_filter)
                case "Block":
                    statements: dict = node["statements"]
                    collector: list[dict] = list()
                    for statement in statements:
                        collector += self._find_node_by_type(statement, type_filter)
                    return collector
                case "VariableDeclarationStatement":
                    return self._find_node_by_type(node["initialValue"], type_filter)
                case _:
                    return []

    def _test_comparison_check(self, smart_contract_name: str, binary_operations: list[dict]) -> bool:
        """
        This function executes the comparison check: it looks for comparison between the two provided
        operands
        :param smart_contract_name: The name of the smart contract to analyze
        :param binary_operations: A list of binary operations that could be performed
        :return: True if the comparison check is valid, False otherwise
        """
        smart_contract_comparisons: list[dict] = self._get_all_comparison_statements(
            smart_contract_name=smart_contract_name)
        if not smart_contract_comparisons:
            logging.debug((colored("No comparisons found", "magenta")))
            return False
        if settings.verbose:
            logging.debug("%s %s", colored("Found Comparisons:", "magenta"),
                          colored(str(len(smart_contract_comparisons)), "cyan"))
            for smart_contract_comparison in smart_contract_comparisons:
                logging.debug("%s %s",
                              colored(f"Line {str(smart_contract_comparison['loc']['end']['line'])}:", "magenta"),
                              colored(self._build_node_string(smart_contract_comparison), "cyan"))
        for provided_operation in binary_operations:
            operand_1: str = provided_operation["operand_1"].lower()
            operand_2: str = provided_operation["operand_2"].lower()
            operator: str = provided_operation["operator"]
            operators: list[str] = [operator, self._reverse_comparison_operand_map[operator]]
            smart_contract_operation_operands: list[tuple] = list()
            for smart_contract_comparison in smart_contract_comparisons:
                smart_contract_operation_operands.append((
                    self._get_statement_operand(smart_contract_comparison["right"]).lower(),
                    self._get_statement_operand(smart_contract_comparison["left"]).lower()))
            if not smart_contract_operation_operands:
                return False
            for (smart_contract_operand_1, smart_contract_operand_2) in smart_contract_operation_operands:
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
        This function executes the inheritance check: it looks for parent names
        :param smart_contract_name: The name of the smart contract to analyze
        :param parent_names: A list of parent names to look for
        :return: True if the inheritance check is valid, False otherwise
        """
        unique_names = set(map(lambda d: d.lower(), parent_names))
        smart_contract_parents: set[str] = self._get_base_contract_names(smart_contract_name=smart_contract_name)
        if not smart_contract_parents:
            return False
        return self._compare_literal(search_for=unique_names, search_in=smart_contract_parents)

    def _test_modifier_check(self, smart_contract_name: str, modifiers: list[str]) -> bool:
        """
        This function executes the modifier check: it looks for definition and/or usage of the provided modifiers
        :param smart_contract_name: The name of the smart contract to analyze
        :param modifiers: A list of modifiers' name to look for
        :return: True if the modifier check is valid, False otherwise
        """
        unique_modifiers: set[str] = set(map(lambda d: d.lower(), modifiers))
        smart_contract_modifiers: set[str] = self._get_modifier_names(smart_contract_name=smart_contract_name)
        if not smart_contract_modifiers:
            return False
        return self._compare_literal(search_for=unique_modifiers, search_in=smart_contract_modifiers)

    def _test_fn_return_parameters_check(self, smart_contract_name: str, provided_parameters: list[dict]) -> bool:
        """
        This function executes the fn_return_parameters check: it looks if exists a function that returns specific types
        :param smart_contract_name: The name of the smart contract to analyze
        :param provided_parameters: A set of return types
        :return: True if the fn_return_parameters check is valid, False otherwise
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        for function in smart_contract_node.functions:
            function_node: dict = smart_contract_node.functions[function]._node
            function_return_parameters: list[dict] = self._get_fn_return_parameters(fn_node=function_node)
            if self._compare_return_parameters(function_return_parameters, provided_parameters=provided_parameters):
                return True
        return False

    def _test_fn_call_check(self, smart_contract_name: str, function_calls: list[str]) -> bool:
        """
        This function executes the fn_call check: it looks for specific functions call
        :param smart_contract_name: The name of the smart contract to analyze
        :param function_calls: A list of function calls
        :return: True if the fn_call check is valid, False otherwise
        """
        smart_contract_function_calls: set[str] = set([self._build_node_string(fn).lower() for fn in
                                                       self._get_all_statements(smart_contract_name=smart_contract_name,
                                                                                type_filter="FunctionCall")])
        unique_function_calls: set[str] = set(map(lambda d: d.lower(), function_calls))
        return self._compare_literal(search_for=unique_function_calls, search_in=smart_contract_function_calls)

    def _test_fn_definition_check(self, smart_contract_name: str, fn_names: list[str]) -> bool:
        """
        This function executes the fn_definition check: it looks for definition of function with a specific name
        :param smart_contract_name: The name of the smart contract to analyze
        :param fn_names: A list of function names
        :return: True if the fn_definition check is valid, False otherwise
        """
        unique_fn_names: set[str] = set(map(lambda d: d.lower(), fn_names))
        smart_contract_fn_names: set[str] = set(map(lambda d: d.lower(),
                                                    self._get_fn_names(smart_contract_name=smart_contract_name)))
        return self._compare_literal(search_for=unique_fn_names, search_in=smart_contract_fn_names)

    def _test_event_emit_check(self, smart_contract_name: str, event_names: list[str]) -> bool:
        """
        This function executes the event_emit check: it looks for definition of event with a specific name
        :param smart_contract_name: The name of the smart contract to analyze
        :param event_names: A list of event names
        :return: True if the event_emit check is valid, False otherwise
        """
        smart_contract_events_names: set[str] = set(map(lambda d: d.lower(),
                                                        self._get_event_names(smart_contract_name=smart_contract_name)))
        unique_event_names: set[str] = set(map(lambda d: d.lower(), event_names))
        return self._compare_literal(search_for=unique_event_names, search_in=smart_contract_events_names)

    def _test_enum_definition_check(self, smart_contract_name: str, enum_names: list[str]) -> bool:
        """
        This function executes the enum_definition check: it looks for definition of enum with a specific name
        :param smart_contract_name: The name of the smart contract to analyze
        :param enum_names: A list of enum names
        :return: True if the enum_definition check is valid, False otherwise
        """
        smart_contract_enum_names: set[str] = set(map(lambda d: d.lower(),
                                                      self._get_enum_names(smart_contract_name=smart_contract_name)))
        unique_enum_names = set(map(lambda d: d.lower(), enum_names))
        return self._compare_literal(search_for=unique_enum_names, search_in=smart_contract_enum_names)

    def _test_state_toggle_check(self, smart_contract_name: str, state_names: list[str]) -> bool:
        """
        This function executes the state_toggle check: it looks for boolean state variable toggles
        :param smart_contract_name: The name of the smart contract to analyze
        :return: True if the state_toggle check is valid, False otherwise
        """
        boolean_states: set[str] = self._get_all_bool_state_vars(smart_contract_name=smart_contract_name)
        assignments: set[str] = set([self._build_node_string(assignment).lower() for assignment in
                                     self._get_all_assignment_statements(smart_contract_name=smart_contract_name)])
        unique_state_names: set[str] = set(map(lambda d: d.lower(), state_names))
        for boolean_state in boolean_states:
            if self._compare_literal(search_for=unique_state_names, search_in={boolean_state}):
                for assignment in assignments:
                    if f"{boolean_state} = !{boolean_state}" == assignment:
                        return True
        return False

    def _test_rejector_check(self, smart_contract_name: str) -> bool:
        """
        This function executes the rejector check: it looks if the contract implements only a rejection fallback
        :param smart_contract_name: The name of the smart contract to analyze
        :return: True if the rejector check is valid, False otherwise
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        smart_contract_functions: list[str] = list(self._get_fn_names(smart_contract_name=smart_contract_name))
        if len(smart_contract_functions) == 1 \
                and smart_contract_functions[0].lower() == "fallback" \
                and smart_contract_node.functions["fallback"].isFallback:
            return self._test_fn_call_check(smart_contract_name=smart_contract_name, function_calls=["revert(*any*)"])
        return False

    def _test_tight_variable_packing_check(self, smart_contract_name: str) -> bool:
        """
        This function executes the tight_variable_packing check: it looks for a struct definition which size is <= 32 bytes
        :param smart_contract_name: The name of the smart contract to analyze
        :return: True if the tight_variable_packing check is valid, False otherwise
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        for struct_name in smart_contract_node.structs:
            if settings.verbose:
                logging.debug("%s '%s'", colored("Found struct:", "magenta"), colored(struct_name, "cyan"))
            struct_size: int = 0
            members: list[dict] = smart_contract_node.structs[struct_name]["members"]
            for member in members:
                if (member["typeName"]["type"] != "ElementaryTypeName") or ("fixed" in member["typeName"]["name"]):
                    struct_size = -1
                    break
                else:
                    struct_size += self._get_data_type_byte_size(member["typeName"]["name"])
            if struct_size != -1 and struct_size <= 32:
                return True
        return False

    def _test_memory_array_building_check(self, smart_contract_name: str) -> bool:
        """
        This function executes the memory_array_building check: it looks a view function with returns a memory array
        :param smart_contract_name: The name of the smart contract to analyze
        :return: True if the memory_array_building check is valid, False otherwise
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        for function in smart_contract_node.functions:
            function_node: dict = smart_contract_node.functions[function]._node
            if function_node["stateMutability"] == "view" and function_node["returnParameters"]:
                memory_array_parameter: dict = {"storage_location": "memory", "type": "ArrayTypeName"}
                function_parameters: list[dict] = self._get_fn_return_parameters(fn_node=function_node)
                return self._compare_return_parameters(function_parameters, [memory_array_parameter])
        return False

    def _test_check_effects_interaction_check(self, smart_contract_name: str) -> bool:
        """
        This function executes the check_effects_interaction check: it looks for an assignment before a fn_call
        :param smart_contract_name: The name of the smart contract to analyze
        :return: True if the check_effects_interaction check is valid, False otherwise
        """
        callable_fn: set[str] = {"send(*any*)", "transfer(*any*)", "call(*any*)"}
        fn_data: dict[str, dict[str, list[int]]] = {}
        for fn_name, fn_statements in self._statements_collector[smart_contract_name]["functions"].items():
            fn_data[fn_name] = {"fn_call_position": [], "assignment_position": []}
            for statement in fn_statements:
                fn_calls: list[dict] = self._find_node_by_type(statement, "FunctionCall")
                assignments: list[dict] = self._find_node_by_type(statement, "BinaryOperation")
                for fn_call in fn_calls:
                    fn_call_string: str = self._build_node_string(fn_call).lower()
                    if self._compare_literal(callable_fn, {fn_call_string}):
                        fn_data[fn_name]["fn_call_position"].append(fn_call["loc"]["end"]["line"])
                for assignment in assignments:
                    if assignment["operator"] in self._assignment_operands:
                        fn_data[fn_name]["assignment_position"].append(assignment["loc"]["end"]["line"])
        for filtered in filter(lambda d: fn_data[d]["fn_call_position"] and fn_data[d]["assignment_position"],
                               fn_data.keys()):
            for assignment_position in fn_data[filtered]["assignment_position"]:
                for fn_call_position in fn_data[filtered]["fn_call_position"]:
                    if (assignment_position + 2) >= fn_call_position:
                        return True
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
            logging.debug("%s '%s'", colored(f"Executing descriptor:", "blue"),
                          colored(descriptor['name'], "cyan"))
        for check in descriptor["checks"]:
            check_type: str = check["check_type"]
            check_result: bool = False
            if check_type not in self._implemented_tests:
                logging.error(colored(f"The check-type: '{check_type}' has not been implemented yet!", "red"))
                continue
            if settings.verbose:
                logging.debug("%s '%s'", colored(f"Testing check:", "blue"), colored(check_type, "cyan"))
            match check_type:
                case "inheritance":
                    check_result = self._test_inheritance_check(smart_contract_name=smart_contract_name,
                                                                parent_names=check["parent_names"])
                case "modifier":
                    check_result = self._test_modifier_check(smart_contract_name=smart_contract_name,
                                                             modifiers=check["modifiers"])
                case "comparison":
                    check_result = self._test_comparison_check(smart_contract_name=smart_contract_name,
                                                               binary_operations=check["binary_operations"])
                case "rejector":
                    check_result = self._test_rejector_check(smart_contract_name=smart_contract_name)
                case "tight_variable_packing":
                    check_result = self._test_tight_variable_packing_check(smart_contract_name=smart_contract_name)
                case "fn_return_parameters":
                    check_result = self._test_fn_return_parameters_check(smart_contract_name=smart_contract_name,
                                                                         provided_parameters=check["parameters_list"])
                case "memory_array_building":
                    check_result = self._test_memory_array_building_check(smart_contract_name=smart_contract_name)
                case "fn_call":
                    check_result = self._test_fn_call_check(smart_contract_name=smart_contract_name,
                                                            function_calls=check["callable_function"])
                case "fn_definition":
                    check_result = self._test_fn_definition_check(smart_contract_name=smart_contract_name,
                                                                  fn_names=check["fn_names"])
                case "event_emit":
                    check_result = self._test_event_emit_check(smart_contract_name=smart_contract_name,
                                                               event_names=check["event_names"])
                case "enum_definition":
                    check_result = self._test_enum_definition_check(smart_contract_name=smart_contract_name,
                                                                    enum_names=check["enum_names"])
                case "check_effects_interaction":
                    check_result = self._test_check_effects_interaction_check(smart_contract_name=smart_contract_name)
                case "state_toggle":
                    check_result = self._test_state_toggle_check(smart_contract_name=smart_contract_name,
                                                                 state_names=check["state_names"])
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
        logging.info("%s '%s'", colored("Analyzing smart-contract: ", "yellow"), colored(smart_contract_name, "cyan"))
        self._collect_statements(smart_contract_name=smart_contract_name)
        results: dict[str, dict[str, bool]] = {}
        for (descriptor_index, descriptor_name) in enumerate(map(lambda d: d["name"], self._descriptors)):
            results[descriptor_name] = self._execute_descriptor(smart_contract_name=smart_contract_name,
                                                                descriptor_index=descriptor_index)
        return results

    def _describe_smart_contract(self, smart_contract_name: str) -> list[dict]:
        """
        This function generate the test's parameters for each generic test
        :param smart_contract_name: The name of the smart contract to describe
        :return: A list of generic tests
        """
        results: list[dict] = []
        if settings.verbose:
            logging.info("%s '%s'", colored("Describing smart-contract: ", "yellow"),
                         colored(smart_contract_name, "cyan"))
        for test_name in self._generic_tests:
            test_keyword: str = ""
            test_parameters: list[dict] | set[str] = set()
            if settings.verbose:
                logging.debug("%s '%s'", colored(f"Looking on check:", "blue"), colored(test_name, "cyan"))
            match test_name:
                case "inheritance":
                    test_parameters = self._get_base_contract_names(smart_contract_name=smart_contract_name)
                    test_keyword = "parent_names"
                case "modifier":
                    test_parameters = self._get_modifier_names(smart_contract_name=smart_contract_name)
                    test_keyword = "modifiers"
                case "comparison":
                    smart_contract_comparisons = self._get_all_comparison_statements(
                        smart_contract_name=smart_contract_name)
                    test_parameters = []
                    for comparison in smart_contract_comparisons:
                        test_parameters.append(
                            {
                                "operator": comparison["operator"],
                                "operand_1": self._build_node_string(comparison["right"]),
                                "operand_2": self._build_node_string(comparison["left"])
                            }
                        )
                    test_keyword = "binary_operations"
                case "fn_return_parameters":
                    smart_contract_fn_return_parameters: dict[str, list[dict]] = self._get_all_fn_return_parameters(
                        smart_contract_name=smart_contract_name)
                    test_parameters = []
                    for parameters_list in smart_contract_fn_return_parameters.values():
                        test_parameters += parameters_list
                    test_keyword = "parameters_list"
                case "fn_call":
                    test_parameters = set([self._build_node_string(fn).lower() for fn in
                                           self._get_all_statements(smart_contract_name=smart_contract_name,
                                                                    type_filter="FunctionCall")])
                    test_keyword = "callable_function"
                case "fn_definition":
                    test_parameters = self._get_fn_names(smart_contract_name=smart_contract_name)
                    test_keyword = "fn_names"
                case "event_emit":
                    test_parameters = self._get_event_names(smart_contract_name=smart_contract_name)
                    test_keyword = "event_names"
                case "enum_definition":
                    test_parameters = self._get_enum_names(smart_contract_name=smart_contract_name)
                    test_keyword = "enum_names"
                case "state_toggle":
                    test_parameters = self._get_all_bool_state_vars(smart_contract_name=smart_contract_name)
                    test_keyword = "state_names"
                case _:
                    logging.error(f"{test_name}  not implemented")
            if test_parameters:
                test_result: dict = {
                    "check_type": test_name,
                    test_keyword: list(test_parameters)
                }
                results.append(test_result)
        return results

    def generate_design_pattern_descriptors(self) -> dict[str, list[dict]]:
        """
        This function generates a design pattern descriptors using the generic tests
        :return: A dictionary containing the generated descriptors for each provided smart-contract
        """
        results: dict[str, list[dict]] = {}
        for smart_contract_name in self._visitor.contracts.keys():
            self._collect_statements(smart_contract_name=smart_contract_name)
            results[smart_contract_name] = self._describe_smart_contract(smart_contract_name=smart_contract_name)
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
