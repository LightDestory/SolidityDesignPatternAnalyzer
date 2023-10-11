import logging
import pprint

from termcolor import colored
from .config import settings
from .solidity_parser.parser import ObjectifyContractVisitor


class SourceUnitExplorer:
    _statement_operand_types: list[str] = [
        "MemberAccess", "NumberLiteral", "stringLiteral", "Identifier", "ElementaryTypeName", "ArrayTypeName",
        "BooleanLiteral", "UserDefinedTypeName", "HexLiteral", "IndexAccess", "HexNumber", "DecimalNumber", "hexLiteral", "StringLiteral"
    ]

    _fixed_data_type_byte_sizes: dict[str, int] = {
        "address": 20,
        "string": 32,
        "bool": 1
    }

    # === EXPLORATION ===

    def collect_definitions(self, smart_contract_node: ObjectifyContractVisitor) -> dict[str, dict[str, list[dict]]]:
        """
        Collects the functions and modifiers of the selected contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A dictionary containing the functions and modifiers of the selected contract
        """
        if settings.verbose:
            logging.debug(colored(f"Collecting statements...", "magenta"))
        collector: dict[str, dict[str, list[dict]]] = {"functions": {}, "modifiers": {}}
        for fn_name, fn_node in smart_contract_node.functions.items():
            if "function()" in fn_name:
                fn_name = "fallback"
            if not fn_node._node.body:
                continue
            collector["functions"][fn_name.lower()] = fn_node._node.body.statements
        for modifier_name, modifier_node in smart_contract_node.modifiers.items():
            collector["modifiers"][modifier_name.lower()] = modifier_node._node.body.statements
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

    def get_all_mapping_state_vars(self, smart_contract_node: ObjectifyContractVisitor) -> dict[str, dict[str, str]]:
        """
        This function returns the name of all the mapping state vars of the specified smart-contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A set of state vars names
        """
        mappings: dict[str, dict[str, str]] = {}
        for var_name, var_node in smart_contract_node.stateVars.items():
            if "type" in var_node["typeName"] and var_node["typeName"][
                "type"] == "Mapping" and var_name.lower() not in mappings:
                mappings[var_name.lower()] = {}
                mappings[var_name.lower()]["visibility"] = var_node["visibility"]
                mappings[var_name.lower()]["loc"] = var_node.loc["start"]["line"]
        return mappings

    def get_base_contract_names(self, smart_contract_node: ObjectifyContractVisitor) -> dict[str, str]:
        """
        This function returns the first-level parent names (inheritance) of a specified smart-contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A set of smart-contract names
        """
        parents: dict[str, str] = {}
        for smart_contract_parent in smart_contract_node._node.baseContracts:
            name: str = smart_contract_parent.baseName.namePath.lower()
            if name not in parents:
                parents[name] = smart_contract_parent.baseName.loc["start"]["line"]
        return parents

    def get_modifier_names(self, smart_contract_node: ObjectifyContractVisitor) -> dict[str, str]:
        """
        This function returns the modifier names defined or used in the specified smart-contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A set of modifier names
        """
        smart_contract_modifiers: dict[str, str] = {}
        for modifier, modifier_node in smart_contract_node.modifiers.items():
            smart_contract_modifiers[modifier.lower()] = modifier_node._node.loc["start"]["line"]
        for function in smart_contract_node.functions:
            for modifier in smart_contract_node.functions[function]._node.modifiers:
                name: str = modifier.name.lower()
                if name not in smart_contract_modifiers:
                    smart_contract_modifiers[name] = modifier.loc["start"]["line"]
        return smart_contract_modifiers

    def get_fn_names(self, smart_contract_node: ObjectifyContractVisitor) -> dict[str, str]:
        """
        This function returns the function names defined in the specified smart-contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A set of function names
        """
        smart_contract_functions: dict[str, str] = {}
        for fn_name, fn_body in smart_contract_node.functions.items():
            name: str = fn_name.lower()
            if "function()" in fn_name:
                name = "fallback"
            if name not in smart_contract_functions:
                smart_contract_functions[name] = fn_body._node.loc["start"]["line"]
        return smart_contract_functions

    def get_event_names(self, smart_contract_node: ObjectifyContractVisitor) -> dict[str, str]:
        """
        This function returns the event names defined in the specified smart-contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A set of event names
        """
        smart_contract_events: dict[str, str] = {}
        for event_name, event_body in smart_contract_node.events.items():
            name: str = event_name.lower()
            if name not in smart_contract_events:
                smart_contract_events[name] = event_body._node.loc["start"]["line"]
        return smart_contract_events

    def get_enum_names(self, smart_contract_node: ObjectifyContractVisitor) -> dict[str, str]:
        """
        This function returns the enum names defined in the specified smart-contract
        :param smart_contract_node: The node of the smart contract to analyze
        :return: A set of enum names
        """
        smart_contract_enums: dict[str, str] = {}
        for enum_name, enum_body in smart_contract_node.enums.items():
            name: str = enum_name.lower()
            if name not in smart_contract_enums:
                smart_contract_enums[name] = enum_body.loc["start"]["line"]
        return smart_contract_enums

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

    def get_all_statements(self, smart_contract_definitions: dict[str, dict[str, list[dict]]], type_filter: str = "") -> \
            list[dict]:
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
                return self.find_node_by_type(node["initialValue"], type_filter) + self.find_node_by_type(
                    node["variables"], type_filter)
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
                                    "TupleExpression", "ThrowStatement"] + self._statement_operand_types:
                return []
            case "InLineAssemblyStatement":
                return self.find_node_by_type(node["body"], type_filter)
            case "AssemblyBlock":
                operations = node["operations"]
                collector: list[dict] = list()
                for op in operations:
                    collector += self.find_node_by_type(op, type_filter)
                return collector
            case "AssemblyAssignment" | "AssemblyLocalDefinition":
                names = node["names"]
                name_collector: list[dict] = list()
                for name in names:
                    name_collector += self.find_node_by_type(name, type_filter)
                return name_collector + self.find_node_by_type(node["expression"], type_filter)
            case "AssemblyExpression":
                args = node["arguments"]
                arg_collector: list[dict] = list()
                for arg in args:
                    arg_collector += self.find_node_by_type(arg, type_filter)
                return arg_collector
            case "AssemblyIf":
                return self.find_node_by_type(node["condition"], type_filter) + \
                    self.find_node_by_type(node["body"], type_filter)
            case "AssemblySwitch":
                cases = node["cases"]
                cases_collector: list[dict] = list()
                for case in cases:
                    cases_collector += self.find_node_by_type(case, type_filter)
                return self.find_node_by_type(node["expression"], type_filter) + cases_collector
            case "AssemblyCase":
                return self.find_node_by_type(node["block"], type_filter)
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
            case "stringLiteral" | "StringLiteral":
                return f"'{wrapped_operand['value']}'"
            case "BooleanLiteral" | "DecimalNumber" | "hexLiteral" | "HexNumber" | "BooleanLiteral" | "HexLiteral":
                return str(wrapped_operand["value"])
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
        if not node:
            logging.warning(colored("None node converted to _", "red"))
            return "_"
        node_type: str = node["type"] if "type" in node else ""
        match node_type:
            case "ReturnStatement":
                return f"return {self.build_node_string(node['expression']) if node['expression'] else ''}"
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
            case "VariableDeclaration":
                return self.build_variable_declaration_string(node)
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
            case "ThrowStatement":
                return "throw"
            case "RevertStatement":
                return f"revert {self.build_node_string(node['functionCall'])}"
            case "UncheckedStatement":
                return f"unchecked {self.build_node_string(node['body'])}"
            case "InLineAssemblyStatement":
                return f"assembly {self.build_node_string(node['body'])}"
            case "AssemblyBlock":
                return f"{{{self.build_assembly_block_string(node)}}}"
            case "AssemblyAssignment" | "AssemblyLocalDefinition":
                return self.build_assembly_assignment_string(node)
            case "AssemblyExpression":
                arguments: list[str] = [self.build_node_string(arg) for arg in node["arguments"]]
                result: str = f"{node['functionName']}"
                result += f"({','.join(arguments)})" if arguments else ""
                return result
            case "AssemblyIf":
                return self.build_assembly_if_string(node)
            case "AssemblySwitch":
                return self.build_assembly_switch_string(node)
            case "AssemblyCase":
                return self.build_assembly_case_string(node)
            case "AssemblyFor":
                return self.build_assembly_for_string(node)
            case "FunctionTypeName":
                return self.build_function_type_name_string(node)
            case _:
                pprint.pprint(node)
                raise ValueError(f"Unable to decode the statement: {node_type}")

    def build_function_call_string(self, call_node: dict) -> str:
        """
        This function recursively inspects a function call to string it
        :param call_node: The call node to analyze
        :return: A stringed function call
        """
        if "name" in call_node:
            function_name: str = call_node['name']
        elif type(call_node["expression"]) == str:
            function_name: str = call_node["expression"]
        else:
            function_name: str = self.build_node_string(call_node["expression"])
        arguments: list[str] = [self.build_node_string(argument) for argument in call_node['arguments']]
        return f"{function_name}({','.join(arguments)})"

    def build_variable_declaration_statement_string(self, declaration_statement_node: dict) -> str:
        """
        This function recursively inspects a variable declaration to string it
        :param declaration_statement_node: The variable declaration statement node to analyze
        :return: A stringed variable declaration
        """
        variables: list[str] = [self.build_node_string(variable) if variable else " "
                                for variable in declaration_statement_node["variables"]]
        declaration_text: str = f"{','.join(variables)}"
        initialization_text: str = ""
        if len(variables) > 1:
            declaration_text = f"({declaration_text})"
        if declaration_statement_node['initialValue']:
            initialization_text = f" = {self.build_node_string(declaration_statement_node['initialValue'])}"
        return f"{declaration_text}{initialization_text}"

    def build_variable_declaration_string(self, variable_node: dict) -> str:
        """
        This function recursively inspects a variable declaration to string it
        :param variable_node: The variable declaration node to analyze
        :return: A stringed variable declaration
        """
        storage_location: str = f"{variable_node['storageLocation']} " if ("storageLocation" in variable_node
                                                                           and variable_node["storageLocation"]) else ""
        type_name: str = ""
        if "typeName" in variable_node and variable_node["typeName"]:
            type_name = f"{self.build_node_string(variable_node['typeName'])} "
        name: str = variable_node["name"] if "name" in variable_node and variable_node["name"] else ""
        return f"{storage_location}{type_name}{name}"

    def build_if_statement_string(self, if_statement_node: dict) -> str:
        """
        This function recursively inspects an if statement to string it
        :param if_statement_node: The if statement node to analyze
        :return: A stringed if statement
        """
        condition_text: str = self.build_node_string(if_statement_node["condition"])
        true_body: str = self.build_node_string(if_statement_node["TrueBody"]) if if_statement_node["TrueBody"] else ""
        false_body: str = f"else {self.build_node_string(if_statement_node['FalseBody'])}" if if_statement_node[
            'FalseBody'] else ""
        return f"if ({condition_text}) {true_body} {false_body}"

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
        init_condition: str = self.build_node_string(for_node["initExpression"]) if for_node["initExpression"] else ""
        condition_expression: str = self.build_node_string(for_node["conditionExpression"])
        loop_expression: str = self.build_node_string(for_node["loopExpression"]) if for_node["loopExpression"] else ""
        return f"for({init_condition}; {condition_expression}; {loop_expression}) {self.build_node_string(for_node['body'])}"

    def build_block_string(self, block_node: dict) -> str:
        """
        This function recursively inspects a block of statements to string it
        :param block_node: The block of statements to analyze
        :return: A stringed block of statements
        """
        statements_text: list[str] = [self.build_node_string(statement) for statement in block_node["statements"]]
        return f"{'; '.join(statements_text)}"

    def build_assembly_block_string(self, assembly_block_node: dict) -> str:
        """
        This function recursively inspects an assembly block of operations to string it
        :param assembly_block_node: The assembly block of operations to analyze
        :return: A stringed assembly block of operations
        """
        operations_text: list[str] = [self.build_node_string(operation)
                                      for operation in assembly_block_node["operations"]]
        return f"{' '.join(operations_text)}"

    def build_assembly_assignment_string(self, assembly_assignment_node: dict) -> str:
        """
        This function recursively inspects an assembly assignment to string it
        :param assembly_assignment_node: The assembly assignment to analyze
        :return: A stringed assembly assignment
        """
        prefix: str = "let " if assembly_assignment_node["type"] == "AssemblyLocalDefinition" else ""
        names: list[str] = [self.build_node_string(k) for k in assembly_assignment_node["names"]]
        return f"{prefix + ','.join(names)} := {self.build_node_string(assembly_assignment_node['expression'])}"

    def build_assembly_if_string(self, assembly_if_node: dict) -> str:
        """
        This function recursively inspects an assembly if to string it
        :param assembly_if_node: The assembly if to analyze
        :return: A stringed assembly if
        """
        condition: str = self.build_node_string(assembly_if_node["condition"])
        body: str = self.build_node_string(assembly_if_node["body"])
        return f"if {condition} {body}"

    def build_assembly_switch_string(self, assembly_switch_node: dict) -> str:
        """
        This function recursively inspects an assembly switch to string it
        :param assembly_switch_node: The assembly switch to analyze
        :return: A stringed assembly switch
        """
        expression: str = self.build_node_string(assembly_switch_node["expression"])
        cases: list[str] = [self.build_node_string(case) for case in assembly_switch_node["cases"]]
        return f"switch {expression} {' '.join(cases)}"

    def build_assembly_case_string(self, assembly_case_node: dict) -> str:
        """
        This function recursively inspects an assembly case to string it
        :param assembly_case_node: The assembly case to analyze
        :return: A stringed assembly case
        """
        if "default" in assembly_case_node and assembly_case_node["default"]:
            prefix: str = "default "
        else:
            prefix: str = f"case {self.build_node_string(assembly_case_node['value'])} "
        return f"{prefix} {self.build_node_string(assembly_case_node['block'])}"

    def build_assembly_for_string(self, assembly_for_node: dict) -> str:
        """
        This function recursively inspects an assembly for to string it
        :param assembly_for_node: The assembly for to analyze
        :return: A stringed assembly for
        """
        pre: str = self.build_node_string(assembly_for_node["pre"])
        condition: str = self.build_node_string(assembly_for_node["condition"])
        post: str = self.build_node_string(assembly_for_node["post"])
        body: str = self.build_node_string(assembly_for_node["body"])
        return f"for {pre} {condition} {post} {body}"

    def build_function_type_name_string(self, function_type_name_node: dict) -> str:
        """
        This function recursively inspects a function type name to string it
        :param function_type_name_node: The function type name to analyze
        :return: A stringed function type name
        """
        returns_type: list[str] = [self.build_node_string(return_type) for return_type in
                                   function_type_name_node["returnTypes"]]
        parameter_types: list[str] = [self.build_node_string(parameter) for parameter in
                                      function_type_name_node["parameterTypes"]]
        stateMutability: str = function_type_name_node[
            "stateMutability"] if "stateMutability" in function_type_name_node else ""
        return f"function ({','.join(parameter_types)}) {stateMutability} returns ({','.join(returns_type)})"

    def build_tuple_string(self, tuple_node: dict) -> str:
        """
        This function recursively inspects a tuple expression to string it
        :param tuple_node: The tuple node to analyze
        :return: A stringed tuple
        """
        components_to_text: list[str] = [self.build_node_string(component) if component else " "
                                         for component in tuple_node["components"]]
        return f"({','.join(components_to_text)})"
