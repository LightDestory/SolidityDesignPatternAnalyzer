import logging
import pprint

from termcolor import colored

from modules.solidity_parser import parser
from modules.config import settings
from modules.utils.utils import ask_confirm


class SolidityScanner:
    _visitor = None  # ObjectifySourceUnitVisitor
    _descriptors: list[dict]
    _statement_operand_types: list[str] = [
        "MemberAccess", "NumberLiteral", "stringLiteral", "Identifier","ElementaryTypeName", "ArrayTypeName",
        "BooleanLiteral", "UserDefinedTypeName"
    ]

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
            case "IndexAccess":
                return f"{self._build_node_string(node['base'])}[{self._build_node_string(node['index'])}]"
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
                return "UDST"

    def _find_literal(self, search_for: list[str], search_in: list[str]) -> bool:
        """
        This function checks if one of the provided item is a sub string or an item of a provided collection
        :param search_for: The list of items to find
        :param search_in: The list of items to search on
        :return: True if there is a match, False otherwise
        """
        for pattern_str in filter(lambda d: "*" in d or "*any*" in d, search_for):
            if settings.verbose:
                logging.debug("{} '{}'".format(colored("Found descriptor's literal pattern:", "magenta"),
                                               colored(pattern_str, "cyan")))
            for smart_contract_item in search_in:
                if settings.verbose:
                    logging.debug("\t{} '{}'".format(colored("Comparing literal pattern with", "magenta"),
                                                     colored(smart_contract_item, "cyan")))
                if "*any*" in pattern_str:
                    pattern_str = pattern_str[:pattern_str.index("*any*")]
                else:
                    pattern_str = pattern_str.replace("*", "")
                if pattern_str in smart_contract_item:
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

    def _get_base_contract_names(self, smart_contract_name: str) -> list[str]:
        """
        This function returns the first-level parent names (inheritance) of a specified smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A list of smart-contract names
        """
        parents: list[str] = list()
        for smart_contract_parent in self._visitor.contracts[smart_contract_name]._node.baseContracts:
            parents.append(smart_contract_parent.baseName.namePath)
        return parents

    def _get_modifier_names(self, smart_contract_name: str) -> list[str]:
        """
        This function returns the modifier names defined or used in the specified smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A list of modifier names
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        smart_contract_modifiers: list[str] = list(smart_contract_node.modifiers.keys())
        for function in smart_contract_node.functions:
            for modifier in smart_contract_node.functions[function]._node.modifiers:
                smart_contract_modifiers.append(modifier.name)
        return smart_contract_modifiers

    def _get_fn_names(self, smart_contract_name: str) -> list[str]:
        """
        This function returns the function names defined in the specified smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A list of function names
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        return list(map(lambda d: smart_contract_node.functions[d]._node["name"],
                        smart_contract_node.functions))

    def _get_event_names(self, smart_contract_name: str) -> list[str]:
        """
        This function returns the event names defined in the specified smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A list of event names
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        return list(map(lambda d: smart_contract_node.functions[d]._node["name"],
                        smart_contract_node.functions))

    def _find_node_by_type(self, node: dict, type_filter: str) -> [dict]:
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
                    return self._find_node_by_type(node["arguments"], type_filter)
                case "IfStatement":
                    return (
                            self._find_node_by_type(node["condition"], type_filter) +
                            self._find_node_by_type(node["TrueBody"], type_filter) +
                            self._find_node_by_type(node["FalseBody"], type_filter)
                    )
                case "Block":
                    statements: dict = node["statements"]
                    collector: list[dict] = list()
                    for statement in statements:
                        collector += self._find_node_by_type(statement, type_filter)
                    return collector
                case _:
                    return []

    def _get_statements(self, smart_contract_name: str, type_filter: str = "") -> list[dict]:
        """
        This function retrieves all the statements of a specific smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :param type_filter: A filter to et only specific statements
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
            result: str = self._build_node_string(statement)
            if "UDST" in result:
                pprint.pprint(statement)
            print("{} {}".format(colored("Rebuilt string:", "green"),
                                 colored(result, "yellow")))
        if not type_filter:
            return statements
        else:
            filtered_statements: list[dict] = list()
            for statement in statements:
                filtered: [dict] = self._find_node_by_type(statement, type_filter)
                if filtered:
                    filtered_statements += filtered
            return filtered_statements

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
            case "stringLiteral" | "BooleanLiteral":
                return f"\"{wrapped_operand['value']}\""
            case "ArrayTypeName":
                length: str = str(wrapped_operand["length"]) if wrapped_operand["length"] else ""
                return f"{self._build_node_string(wrapped_operand['baseTypeName'])}[{length}]"
            case "UserDefinedTypeName":
                return wrapped_operand["namePath"]
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
        binary_operation_node: list[dict] = self._get_statements(smart_contract_name=smart_contract_name,
                                                                 type_filter="BinaryOperation")
        operand_1 = operand_1.lower()
        operand_2 = operand_2.lower()
        operators: list[str] = [operator, self._get_comparison_reverse_operator(operator)]
        smart_contract_operation_operands: list[tuple] = list()
        for operation in binary_operation_node:
            smart_contract_operation_operands.append((
                self._get_statement_operand(operation["right"]).lower(),
                self._get_statement_operand(operation["left"]).lower()))
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
        parent_names = list(map(lambda d: d.lower(), parent_names))
        smart_contract_parents: list[str] = list(
            map(lambda d: d.lower(), self._get_base_contract_names(smart_contract_name=smart_contract_name)))
        return self._find_literal(search_for=parent_names, search_in=smart_contract_parents)

    def _test_modifier_check(self, smart_contract_name: str, modifiers: list[str]) -> bool:
        """
        This function executes the modifier check: it looks for definition and/or usage of the provided modifiers
        :param smart_contract_name: The name of the smart contract to analyze
        :param modifiers: A list of modifiers' name to look for
        :return: True if the modifier check is valid, False otherwise
        """
        modifiers: list[str] = list(map(lambda d: d.lower(), modifiers))
        smart_contract_modifiers: list[str] = list(
            set(map(lambda d: d.lower(), self._get_modifier_names(smart_contract_name=smart_contract_name))))
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
            return self._test_usage_of_fn_check(smart_contract_name=smart_contract_name,
                                                function_calls=["revert(*any*)"])
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

    def _test_fn_return_parameters_check(self, fn_return_parameters: list[dict],
                                         provided_parameters: list[dict]) -> bool:
        """
        This function executes the fn_return_parameters check: it looks if a function that returns specific types
        :param fn_return_parameters: The returnParameters node of a function to analyze
        :param provided_parameters: A set of return types
        :return: True if the tight_variable_packing check is valid, False otherwise
        """
        if len(fn_return_parameters) >= len(provided_parameters):
            provided_parameters_shadow: list[dict] = provided_parameters.copy()
            for provided_parameter in provided_parameters:
                for smart_contract_fn_parameter in fn_return_parameters:
                    if smart_contract_fn_parameter["storageLocation"] == provided_parameter["storageLocation"] and \
                            smart_contract_fn_parameter["typeName"]["type"] == provided_parameter["typeName"]:
                        provided_parameters_shadow.remove(provided_parameter)
                        fn_return_parameters.remove(smart_contract_fn_parameter)
                        break
            if len(provided_parameters_shadow) == 0:
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
                memory_array_parameter: dict = {
                    "storageLocation": "memory",
                    "typeName": "ArrayTypeName"
                }
                return self._test_fn_return_parameters_check(function_node["returnParameters"]["parameters"],
                                                             [memory_array_parameter])
        return False

    def _test_usage_of_fn_check(self, smart_contract_name: str, function_calls: list[str]) -> bool:
        """
        This function executes the usage_of_fn check: it looks for specific functions call
        :param smart_contract_name: The name of the smart contract to analyze
        :param function_calls: A list of function calls
        :return: True if the usage_of_fn check is valid, False otherwise
        """
        smart_contract_function_calls: list[str] = [self._build_node_string(fn).lower() for fn in
                                                    self._get_statements(smart_contract_name=smart_contract_name,
                                                                         type_filter="FunctionCall")]
        function_calls = list(map(lambda d: d.lower(), function_calls))
        return self._find_literal(search_for=function_calls, search_in=smart_contract_function_calls)

    def _test_fn_definition_check(self, smart_contract_name: str, fn_names: list[str]) -> bool:
        """
        This function executes the fn_definition check: it looks for definition of function with a specific name
        :param smart_contract_name: The name of the smart contract to analyze
        :param fn_names: A list of function names
        :return: True if the fn_definition check is valid, False otherwise
        """
        smart_contract_fn_names: list[str] = self._get_fn_names(smart_contract_name=smart_contract_name)
        fn_names = list(map(lambda d: d.lower(), fn_names))
        smart_contract_fn_names = list(map(lambda d: d.lower(), smart_contract_fn_names))
        return self._find_literal(search_for=fn_names, search_in=smart_contract_fn_names)

    def _test_event_emit_check(self, smart_contract_name: str, event_names: list[str]) -> bool:
        """
        This function executes the event_emit check: it looks for definition of event with a specific name
        :param smart_contract_name: The name of the smart contract to analyze
        :param event_names: A list of event names
        :return: True if the event_emit check is valid, False otherwise
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        smart_contract_events_names: list[str] = list(map(lambda d: d.lower(), smart_contract_node.events.keys()))
        event_names = list(map(lambda d: d.lower(), event_names))
        return self._find_literal(search_for=event_names, search_in=smart_contract_events_names)

    def _test_enum_definition_check(self, smart_contract_name: str, enum_names: list[str]) -> bool:
        """
        This function executes the enum_definition check: it looks for definition of enum with a specific name
        :param smart_contract_name: The name of the smart contract to analyze
        :param enum_names: A list of enum names
        :return: True if the enum_definition check is valid, False otherwise
        """
        smart_contract_node = self._visitor.contracts[smart_contract_name]
        smart_contract_events_names: list[str] = list(map(lambda d: d.lower(), smart_contract_node.enums.keys()))
        enum_names = list(map(lambda d: d.lower(), enum_names))
        return self._find_literal(search_for=enum_names, search_in=smart_contract_events_names)

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
                case "usage_of_fn":
                    check_result = self._test_usage_of_fn_check(smart_contract_name=smart_contract_name,
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
