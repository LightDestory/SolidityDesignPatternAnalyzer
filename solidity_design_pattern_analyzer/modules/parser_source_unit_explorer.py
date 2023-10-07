import logging
import pprint

from termcolor import colored
from .config import settings
from .solidity_parser.parser import ObjectifyContractVisitor


class SourceUnitExplorer:
    _statement_operand_types: list[str] = [
        "MemberAccess", "NumberLiteral", "stringLiteral", "Identifier", "ElementaryTypeName", "ArrayTypeName",
        "BooleanLiteral", "UserDefinedTypeName", "HexLiteral", "IndexAccess"
    ]

    _fixed_data_type_byte_sizes: dict[str, int] = {
        "address": 20,
        "string": 32,
        "bool": 1
    }

    # === EXPLORATION ===

    def collect_definition(self, smart_contract_node: ObjectifyContractVisitor) -> dict[str, dict[str, list[dict]]]:
        """
        Collects the functions and modifiers of the selected contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A dictionary containing the functions and modifiers of the selected contract
        """
        if settings.verbose:
            logging.debug(colored(f"Collecting statements...", "magenta"))
        collector: dict[str, dict[str, list[dict]]] = {"functions": {}, "modifiers": {}}
        for fn_name in smart_contract_node.functions:
            if not smart_contract_node.functions[fn_name]._node.body:
                continue
            collector["functions"][fn_name.lower()] = \
                smart_contract_node.functions[fn_name]._node.body.statements
        for modifier_name in smart_contract_node.modifiers:
            collector["modifiers"][modifier_name.lower()] = \
                smart_contract_node.modifiers[modifier_name]._node.body.statements
        if settings.verbose:
            for item_type in ["functions", "modifiers"]:
                for name, statements in collector[item_type].items():
                    logging.debug("%s %s", colored(f"Rebuilding {item_type}:", "magenta"), colored(name, "cyan"))
                    for statement in statements:
                        result: str = self.build_node_string(statement)
                        logging.debug(
                            "\t%s %s", colored("Rebuilt statement:", "magenta"), colored(result, "cyan"))
        return collector

    def get_all_bool_state_vars(self, smart_contract_node: ObjectifyContractVisitor) -> set[str]:
        """
        This function returns the name of all the boolean state vars of the specified smart-contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A set of state vars names
        """
        return set([k.lower() for k, v in smart_contract_node.stateVars.items() if
                    "name" in v["typeName"] and v["typeName"]["name"] == "bool"])

    def get_all_mapping_state_vars(self, smart_contract_node: ObjectifyContractVisitor) -> dict[str, str]:
        """
        This function returns the name of all the mapping state vars of the specified smart-contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A set of state vars names
        """
        mappings: dict[str, str] = {}
        for var_name, var_node in smart_contract_node.stateVars.items():
            if "type" in var_node["typeName"] and var_node["typeName"]["type"] == "Mapping":
                mappings[var_name.lower()] = var_node["visibility"]
        return mappings

    def get_base_contract_names(self, smart_contract_node: ObjectifyContractVisitor) -> set[str]:
        """
        This function returns the first-level parent names (inheritance) of a specified smart-contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A set of smart-contract names
        """
        parents: set[str] = set()
        for smart_contract_parent in smart_contract_node._node.baseContracts:
            parents.add(smart_contract_parent.baseName.namePath.lower())
        return parents

    def get_modifier_names(self, smart_contract_node: ObjectifyContractVisitor) -> set[str]:
        """
        This function returns the modifier names defined or used in the specified smart-contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A set of modifier names
        """
        smart_contract_modifiers: set[str] = set([name.lower() for name in smart_contract_node.modifiers])
        for function in smart_contract_node.functions:
            for modifier in smart_contract_node.functions[function]._node.modifiers:
                smart_contract_modifiers.add(modifier.name.lower())
        return smart_contract_modifiers

    def get_fn_names(self, smart_contract_node: ObjectifyContractVisitor) -> set[str]:
        """
        This function returns the function names defined in the specified smart-contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A set of function names
        """
        return set([name.lower() for name in smart_contract_node.functions])

    def get_event_names(self, smart_contract_node: ObjectifyContractVisitor) -> set[str]:
        """
        This function returns the event names defined in the specified smart-contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A set of event names
        """
        return set(map(lambda d: smart_contract_node.events[d]._node["name"].lower(),
                       smart_contract_node.events))

    def get_enum_names(self, smart_contract_node: ObjectifyContractVisitor) -> set[str]:
        """
        This function returns the enum names defined in the specified smart-contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A set of enum names
        """
        return set(map(lambda d: d.lower(), smart_contract_node.enums.keys()))

    def get_fn_return_parameters(self, fn_node: dict) -> list[dict]:
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
        unique_return_parameters: list[dict] = [dict(t) for t in {tuple(d.items()) for d in return_parameters}]
        return unique_return_parameters

    def get_all_fn_return_parameters(self, smart_contract_node: ObjectifyContractVisitor) -> dict[str, list[dict]]:
        """
        This function returns all the return parameters of all the smart-contract's functions
        :param smart_contract_node:The node of the smart contract to analyze
        :return: A list of return parameters containing storage location and type for each smart-contract's function
        """
        return_parameters: dict[str, list[dict]] = {}
        for function in smart_contract_node.functions:
            function_node: dict = smart_contract_node.functions[function]._node
            if not function_node["returnParameters"]:
                continue
            parameters: list[dict] = self.get_fn_return_parameters(function_node)
            if parameters:
                return_parameters[function] = parameters
        return return_parameters

    def get_all_statements(self, smart_contract_definitions: dict[str, dict[str, list[dict]]], type_filter: str = "") -> list[dict]:
        """
        This function retrieves all the statements of a specific smart-contract
        :param smart_contract_definitions: The definitions of the smart-contract to analyze
        :param type_filter: A filter to et only specific statements
        :return: A list of all the first-level statements
        """
        statements_pool: list[dict] = []
        for item_type in ["functions", "modifiers"]:
            for name, statements in smart_contract_definitions[item_type].items():
                statements_pool += statements
        if not type_filter:
            return statements_pool
        else:
            return self.filter_statements_pool(statements_pool=statements_pool, type_filter=type_filter)

    def filter_statements_pool(self, statements_pool: list[dict], type_filter: str) -> list[dict]:
        """
        This function takes in input a list of statements and filters them using a user-provided filter
        :param statements_pool: A list of unfiltered statements
        :param type_filter: A filter to et only specific statements
        :return: A list of filtered statements
        """
        filtered_statements: list[dict] = list()
        for statement in statements_pool:
            filtered: list[dict] = self.find_node_by_type(statement, type_filter)
            if filtered:
                filtered_statements += filtered
        return filtered_statements

    def find_node_by_type(self, node: dict, type_filter: str) -> list[dict]:
        """
        This function recursively inspects a node to find a specific sub-nodes
        :param node: The root node to analyze
        :param type_filter: The node type to look for
        :return: A list of filtered nodes
        """
        if not node:
            return []
        if "type" not in node:
            pprint.pprint(node)
            raise ValueError(f"Unable to identify node!")
        node_type: str = node["type"]
        if node_type == type_filter:
            return [node] + self._find_navigator(node, type_filter)
        else:
            return self._find_navigator(node, type_filter)

    def _find_navigator(self, node: dict, type_filter: str) -> list[dict]:
        """
        This function navigates all the provided node's branches to find a sub-nodes
        :param node: The root node to analyze
        :param type_filter: The node type to look for
        :return: A list of sub-nodes
        """
        node_type: str = node["type"]
        match node_type:
            case "ReturnStatement":
                return self.find_node_by_type(node["expression"], type_filter)
            case "EmitStatement":
                return self.find_node_by_type(node["eventCall"], type_filter)
            case "ExpressionStatement":
                return self.find_node_by_type(node["expression"], type_filter)
            case "RevertStatement":
                return self.find_node_by_type(node['functionCall'], type_filter)
            case "FunctionCall":
                arguments: dict = node["arguments"]
                collector: list[dict] = list()
                if type(node["expression"]) != str:
                    collector += self.find_node_by_type(node["expression"], type_filter)
                for argument in arguments:
                    collector += self.find_node_by_type(argument, type_filter)
                return collector
            case "IfStatement":
                return self.find_node_by_type(node["condition"], type_filter) + \
                    self.find_node_by_type(node["TrueBody"], type_filter) + \
                    self.find_node_by_type(node["FalseBody"], type_filter)
            case "WhileStatement" | "DoWhileStatement":
                return self.find_node_by_type(node["condition"], type_filter) + \
                    self.find_node_by_type(node["body"], type_filter)
            case "ForStatement":
                return self.find_node_by_type(node["initExpression"], type_filter) + \
                    self.find_node_by_type(node["conditionExpression"], type_filter) + \
                    self.find_node_by_type(node["loopExpression"], type_filter) + \
                    self.find_node_by_type(node["body"], type_filter)
            case "Block":
                statements: dict = node["statements"]
                collector: list[dict] = list()
                for statement in statements:
                    collector += self.find_node_by_type(statement, type_filter)
                return collector
            case "VariableDeclarationStatement":
                return self.find_node_by_type(node["initialValue"], type_filter)
            case "BinaryOperation":
                return self.find_node_by_type(node["left"], type_filter) + \
                    self.find_node_by_type(node["right"], type_filter)
            case "UnaryOperation":
                return self.find_node_by_type(node["subExpression"], type_filter)
            case "Conditional":
                return self.find_node_by_type(node["condition"], type_filter)
            case "UncheckedStatement":
                return self.find_node_by_type(node['body'], type_filter)
            case _ if node_type in ["ContinueStatement", "BreakStatement", "NewExpression",
                                    "TupleExpression"] + self._statement_operand_types:
                return []
            case _:
                pprint.pprint(node)
                raise ValueError(f"Unknown navigation route for {node_type}")

    def get_all_comparison_statements(self, smart_contract_definitions: dict[str, dict[str, list[dict]]],
                                      reverse_comparison_operand_map: dict[str, str]) -> list[dict]:
        """
        This function returns all the Binary Operations that uses a comparison operator
        :param smart_contract_definitions: The definitions of the smart-contract to analyze
        :param reverse_comparison_operand_map: A map of comparison operators
        :return: A list of comparison statements
        """
        return list(filter(lambda d: d["operator"] in reverse_comparison_operand_map.keys(),
                           self.get_all_statements(smart_contract_definitions=smart_contract_definitions,
                                                   type_filter="BinaryOperation")))

    def get_all_assignment_statements(self, smart_contract_definitions: dict[str, dict[str, list[dict]]],
                                      assignment_operands: list[str]) -> list[dict]:
        """
        This function returns all the Binary Operations that uses an assigment operator
        :param smart_contract_definitions: The definitions of the smart-contract to analyze
        :param assignment_operands: A list of assignment operators
        :return: A list of assignment statements
        """
        return list(filter(lambda d: d["operator"] in assignment_operands,
                           self.get_all_statements(smart_contract_definitions=smart_contract_definitions,
                                                   type_filter="BinaryOperation")))

    def get_data_type_byte_size(self, data_type_name: str) -> int:
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
        raise ValueError(f"Unsupported data type: {data_type_name}")

    def get_statement_operand(self, wrapped_operand: dict) -> str:
        """
        This function unwraps an operand and returns the string literal
        :param wrapped_operand: The operand object of a condition
        :return: The operand string literal
        """
        operand_type: str = wrapped_operand["type"] if wrapped_operand["type"] else "Identifier"
        match operand_type:
            case "MemberAccess":
                return f"{self.build_node_string(wrapped_operand['expression'])}.{wrapped_operand['memberName']}"
            case "FunctionCall":
                return self.build_function_call_string(wrapped_operand)
            case "BinaryOperation" | "UnaryOperation":
                return self.build_node_string(wrapped_operand)
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
                return f"{self.build_node_string(wrapped_operand['baseTypeName'])}[{length}]"
            case "UserDefinedTypeName":
                return wrapped_operand["namePath"]
            case "IndexAccess":
                return f"{self.build_node_string(wrapped_operand['base'])}[{self.build_node_string(wrapped_operand['index'])}]"
            case _:
                raise ValueError(f"Unsupported operand type: {operand_type}")

    # === STRING BUILDER ===

    def build_node_string(self, node: dict) -> str:
        """
        This function recursively inspects a node to string it
        :param node: The node to analyze
        :return: A stringed node
        """
        node_type: str = node["type"] if "type" in node else ""
        match node_type:
            case "ReturnStatement":
                return f"return {self.build_node_string(node['expression'])}"
            case "EmitStatement":
                return f"emit {self.build_node_string(node['eventCall'])}"
            case "ExpressionStatement":
                return self.build_node_string(node['expression'])
            case "FunctionCall" | "FunctionCallOptions":
                return self.build_function_call_string(node)
            case "UnaryOperation":
                if node["isPrefix"]:
                    return f"{node['operator']}{self.build_node_string(node['subExpression'])}"
                return f"{self.build_node_string(node['subExpression'])}{node['operator']}"
            case "BinaryOperation":
                return f"{self.build_node_string(node['left'])} {node['operator']} {self.build_node_string(node['right'])}"
            case node_type if node_type in self._statement_operand_types:
                return self.get_statement_operand(node)
            case "VariableDeclarationStatement":
                return self.build_variable_declaration_statement_string(node)
            case "IfStatement":
                return self.build_if_statement_string(node)
            case "WhileStatement" | "DoWhileStatement":
                return self.build_while_loop_string(node)
            case "ForStatement":
                return self.build_for_loop_string(node)
            case "NewExpression":
                return f"new {self.build_node_string(node['typeName'])}"
            case "Block":
                return f"{{{self.build_block_string(node)}}}"
            case "Conditional":
                return f"{self.build_node_string(node['condition'])} ? {self.build_node_string(node['TrueExpression'])} : {self.build_node_string(node['FalseExpression'])}"
            case "TupleExpression":
                return self.build_tuple_string(node)
            case "BreakStatement":
                return "break"
            case "ContinueStatement":
                return "continue"
            case "RevertStatement":
                return f"revert {self.build_node_string(node['functionCall'])}"
            case "UncheckedStatement":
                return f"unchecked {self.build_node_string(node['body'])}"
            case _:
                pprint.pprint(node)
                raise ValueError(f"Unable to decode the statement: {node_type}")

    def build_function_call_string(self, call_node: dict) -> str:
        """
        This function recursively inspects a function call to string it
        :param call_node: The call node to analyze
        :return: A stringed function call
        """
        function_name: str
        if "name" in call_node:
            function_name = call_node['name']
        elif type(call_node["expression"]) == str:
            function_name = call_node["expression"]
        else:
            function_name = self.build_node_string(call_node["expression"])
        function_call: str = f"{function_name}("
        arguments: list[dict] = call_node['arguments']
        for index, argument in enumerate(arguments):
            function_call += f"{self.build_node_string(argument)}"
            if index < len(arguments) - 1:
                function_call += ", "
        function_call += ")"
        return function_call

    def build_variable_declaration_statement_string(self, declaration_node: dict) -> str:
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
            declaration_text += f"{self.build_node_string(variable['typeName'])}{storage_location}{variable['name']}"
            if index < len(variables) - 1:
                declaration_text += ", "
        declaration_text += ")" if len(variables) > 1 else ""
        if declaration_node['initialValue']:
            initialization_text = f" = {self.build_node_string(declaration_node['initialValue'])}"
        return f"{declaration_text}{initialization_text}"

    def build_if_statement_string(self, if_statement_node: dict) -> str:
        """
        This function recursively inspects an if statement to string it
        :param if_statement_node: The if statement node to analyze
        :return: A stringed if statement
        """
        condition_text: str = self.build_node_string(if_statement_node["condition"])
        true_body: str = self.build_node_string(if_statement_node["TrueBody"])
        false_body: str = ""
        if if_statement_node["FalseBody"]:
            false_body: str = f"else {self.build_node_string(if_statement_node['FalseBody'])}"
        return f"if {condition_text} {true_body} {false_body}"

    def build_while_loop_string(self, while_node: dict) -> str:
        """
        This function recursively inspects a while/do while loop to string it
        :param while_node: The while/do while loop node to analyze
        :return: A stringed while/do while loop
        """
        loop_type: str = while_node["type"]
        condition_text: str = self.build_node_string(while_node["condition"])
        loop_body: str = self.build_node_string(while_node["body"])
        if loop_type == "WhileStatement":
            return f"while ({condition_text}) {loop_body}"
        else:
            return f"do {loop_body} while({condition_text})"

    def build_for_loop_string(self, for_node: dict) -> str:
        """
        This function recursively inspects a for loop to string it
        :param for_node: The for node to analyze
        :return: A stringed for loop
        """
        init_condition: str = self.build_node_string(for_node["initExpression"])
        condition_expression: str = self.build_node_string(for_node["conditionExpression"])
        loop_expression: str = self.build_node_string(for_node["loopExpression"])
        return f"for({init_condition}; {condition_expression}; {loop_expression}) {self.build_node_string(for_node['body'])}"

    def build_block_string(self, block_node: dict) -> str:
        """
        This function recursively inspects a block of statements to string it
        :param block_node: The block of statements to analyze
        :return: A stringed block of statements
        """
        statements: list[dict] = block_node["statements"]
        statements_text = ""
        for statement in statements:
            statements_text += f"{self.build_node_string(statement)}; "
        return statements_text

    def build_tuple_string(self, tuple_node: dict) -> str:
        """
        This function recursively inspects a tuple expression to string it
        :param tuple_node: The tuple node to analyze
        :return: A stringed tuple
        """
        components: list[dict] = tuple_node["components"]
        declaration_text: str = "("
        for index, component in enumerate(components):
            declaration_text += f"{self.build_node_string(component)}"
            if index < len(components) - 1:
                declaration_text += ", "
        declaration_text += ")"
        return declaration_text
