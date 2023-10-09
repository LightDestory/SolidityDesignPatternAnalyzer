import logging
import pprint

from termcolor import colored

from .parser_source_unit_explorer import SourceUnitExplorer
from .solidity_parser import parser
from .config import settings
from .solidity_parser.parser import ObjectifySourceUnitVisitor, ObjectifyContractVisitor
from .utils.utils import ask_confirm


class SolidityScanner:
    _visitor: ObjectifySourceUnitVisitor = None
    _source_unit_explorer: SourceUnitExplorer = SourceUnitExplorer()
    _implemented_tests: list[str]
    _generic_tests: list[str] = [
        "comparison", "inheritance", "modifier", "fn_return_parameters", "fn_call", "fn_definition", "event_emit",
        "enum_definition", "state_toggle"
    ]
    _specialized_tests: list[str] = [
        "rejector", "tight_variable_packing", "memory_array_building", "check_effects_interaction", "relay",
        "eternal_storage"
    ]
    _reverse_comparison_operand_map: dict[str, str] = {
        ">": "<",
        "<": ">",
        "<=": ">=",
        ">=": "<=",
        "==": "==",
        "!=": "!="
    }
    _assignment_operands: list[str] = ["=", "+=", "-="]
    _current_smart_contract_node: ObjectifyContractVisitor = None
    _current_smart_contract_definitions: dict[str, dict[str, list[dict]]] = {}

    # === PRE-LOADING FUNCTIONS ===

    def __init__(self):
        self._implemented_tests = self._generic_tests + self._specialized_tests

    def parse_solidity_file(self, solidity_file_path: str) -> bool:
        """
        This function parses the solidity source code file provided and stores a visitor
        :param solidity_file_path: A valid solidity source code file path
        :return: True if parsed successfully, False otherwise
        """
        try:
            self._visitor = parser.objectify(
                parser.parse_file(solidity_file_path, loc=True))
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
        if settings.allow_incompatible == "always":
            return True
        loaded_version: str = "Unknown"
        for pragma in self._visitor.pragmas:
            if pragma["name"] == "solidity":
                loaded_version = pragma["value"]
        if loaded_version != settings.solidity_version:
            if settings.allow_incompatible == "ask":
                logging.warning("%s '%s'\t%s '%s'",
                                colored("Compatible Version:", "magenta"),
                                colored(settings.solidity_version, "cyan"),
                                colored("Loaded Version:", "magenta"),
                                colored(loaded_version, "cyan")
                                )
                logging.warning(
                    colored("The provided solidity source code file's version is not compatible.", "magenta"))
                user_confirm: bool = ask_confirm("Proceed anyway?")
                if not user_confirm:
                    logging.info(colored("Skipping...", "yellow"))
                return user_confirm
            else:
                return False
        return True

    # === SMART CONTRACT'S ANALYSIS FUNCTIONS ===

    def get_design_pattern_statistics(self) -> dict[str, dict[str, dict[str, dict[str, bool | str]]]]:
        """
        This function looks for design pattern usages in each provided smart-contract and return a statistic based on
        provided descriptors' checks
        :return: A dictionary containing the statistics for each provided smart-contract
        """
        results: dict[str, dict[str, dict[str, dict[str, bool | str]]]] = {}
        for smart_contract_name in self._visitor.contracts.keys():
            results[smart_contract_name] = self._find_design_pattern_usage(smart_contract_name=smart_contract_name)
        return results

    def _find_design_pattern_usage(self, smart_contract_name: str) -> dict[str, dict[str, dict[str, bool | str]]]:
        """
        This function executes the provided descriptors against the selected smart-contract
        :param smart_contract_name: The name of the smart contract to analyze
        :return: A dictionary containing the usage statistics of each provided descriptor for the selected smart-contract
        """
        logging.info("%s '%s'", colored("Analyzing smart-contract: ", "yellow"), colored(smart_contract_name, "cyan"))
        self._current_smart_contract_node = self._visitor.contracts[smart_contract_name]
        self._current_smart_contract_definitions = self._source_unit_explorer.collect_definitions(
            self._current_smart_contract_node)
        results: dict[str, dict[str, dict[str, bool | str]]] = {}
        for (descriptor_index, descriptor_name) in enumerate(map(lambda d: d["name"], settings.descriptors)):
            results[descriptor_name] = self._execute_descriptor(descriptor_index=descriptor_index)
        return results

    def _execute_descriptor(self, descriptor_index: int) -> dict[str, dict[str, bool | str]]:
        """
        This function tests all the selected descriptor's checks
        :param descriptor_index: The index of the descriptor to execute
        :return: The validated status for each descriptor's checks
        """
        results: dict[str, dict[str, bool | str]] = {}
        descriptor: dict = settings.descriptors[descriptor_index]
        if settings.verbose:
            logging.debug("%s '%s'", colored(f"Executing descriptor:", "blue"),
                          colored(descriptor['name'], "cyan"))
        for check in descriptor["checks"]:
            check_type: str = check["check_type"]
            check_result: dict[str, bool | str] = {"result": False}
            if check_type not in self._implemented_tests:
                logging.error(colored(f"The check-type: '{check_type}' has not been implemented yet!", "red"))
                continue
            if settings.verbose:
                logging.debug("%s '%s'", colored(f"Testing check:", "blue"), colored(check_type, "cyan"))
            match check_type:
                case "inheritance":
                    check_result = self._test_inheritance_check(parent_names=check["parent_names"])
                case "modifier":
                    check_result = self._test_modifier_check(modifiers=check["modifiers"])
                case "comparison":
                    check_result = self._test_comparison_check(binary_operations=check["binary_operations"])
                case "rejector":
                    check_result = self._test_rejector_check()
                case "tight_variable_packing":
                    check_result = self._test_tight_variable_packing_check()
                case "fn_return_parameters":
                    check_result = self._test_fn_return_parameters_check(provided_parameters=check["parameters_list"])
                case "memory_array_building":
                    check_result = self._test_memory_array_building_check()
                case "fn_call":
                    check_result = self._test_fn_call_check(function_calls=check["callable_function"])
                case "fn_definition":
                    check_result = self._test_fn_definition_check(fn_names=check["fn_names"])
                case "event_emit":
                    check_result = self._test_event_emit_check(event_names=check["event_names"])
                case "enum_definition":
                    check_result = self._test_enum_definition_check(enum_names=check["enum_names"])
                case "check_effects_interaction":
                    check_result = self._test_check_effects_interaction_check()
                case "state_toggle":
                    check_result = self._test_state_toggle_check(state_names=check["state_names"])
                case "relay":
                    check_result = self._test_relay_check()
                case "eternal_storage":
                    check_result = self._test_eternal_storage_check()
            if settings.verbose:
                if check_result["result"]:
                    logging.debug(colored("Test passed!", "green"))
                else:
                    logging.debug(colored("Test failed!", "red"))
            results[check_type] = check_result
        return results

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

    def _compare_literal(self, search_for: set[str], search_in: set[str]) -> (bool, str):
        """
        This function checks if one of the provided item is a sub string or an item of a provided collection
        :param search_for: The list of items to find
        :param search_in: The list of items to search on
        :return: True if there is a match, False otherwise
        """
        string_patters: list[str] = list(sorted(filter(lambda d: "*" in d, search_for)))
        if string_patters:
            if settings.verbose:
                logging.debug("%s '%s'", colored("Checking descriptor's string patterns:", "magenta"),
                              colored(pprint.pformat(string_patters), "cyan"))
            for pattern_str in string_patters:
                if "*any*" in pattern_str:
                    pattern_str = pattern_str[:pattern_str.index("*any*")]
                else:
                    pattern_str = pattern_str.replace("*", "")
                for smart_contract_item in sorted(search_in):
                    if pattern_str in smart_contract_item:
                        return True, smart_contract_item
        string_literals: list[str] = list(sorted(filter(lambda d: "*" not in d, search_for)))
        if string_literals:
            if settings.verbose:
                logging.debug("%s '%s'", colored("Checking descriptor's string literals:", "magenta"),
                              colored(pprint.pformat(string_literals), "cyan"))
            for item in string_literals:
                for smart_contract_item in sorted(search_in):
                    if item == smart_contract_item:
                        return True, smart_contract_item
        return False, ""

    def _test_inheritance_check(self, parent_names: list[str]) -> dict[str, bool | str]:
        """
        This function executes the inheritance check: it looks for parent names
        :param parent_names: A list of parent names to look for
        :return: True if the inheritance check is valid, False otherwise
        """
        unique_names = set(map(lambda d: d.lower(), parent_names))
        smart_contract_parents: dict[str, str] = self._source_unit_explorer.get_base_contract_names(
            self._current_smart_contract_node)
        if not smart_contract_parents:
            return {"result": False}
        result, trigger = self._compare_literal(search_for=unique_names, search_in=set(smart_contract_parents.keys()))
        if not result:
            return {"result": False}
        else:
            return {"result": True, "line_match": smart_contract_parents[trigger], "match_statement": trigger}

    def _test_modifier_check(self, modifiers: list[str]) -> dict[str, bool | str]:
        """
        This function executes the modifier check: it looks for definition and/or usage of the provided modifiers
        :param modifiers: A list of modifiers' name to look for
        :return: True if the modifier check is valid, False otherwise
        """
        unique_modifiers: set[str] = set(map(lambda d: d.lower(), modifiers))
        smart_contract_modifiers: dict[str, str] = self._source_unit_explorer.get_modifier_names(
            self._current_smart_contract_node)
        if not smart_contract_modifiers:
            return {"result": False}
        result, trigger = self._compare_literal(search_for=unique_modifiers,
                                                search_in=set(smart_contract_modifiers.keys()))
        if not result:
            return {"result": False}
        else:
            return {"result": True, "line_match": smart_contract_modifiers[trigger], "match_statement": trigger}

    def _test_comparison_check(self, binary_operations: list[dict]) -> dict[str, bool | str]:
        """
        This function executes the comparison check: it looks for comparison between the two provided
        operands
        :param binary_operations: A list of binary operations that could be performed
        :return: True if the comparison check is valid, False otherwise
        """
        smart_contract_comparisons: list[dict] = self._source_unit_explorer.get_all_comparison_statements(
            self._current_smart_contract_definitions, self._reverse_comparison_operand_map)
        smart_contract_operation_description: list[tuple] = list()
        if not smart_contract_comparisons:
            logging.debug((colored("No comparisons found", "magenta")))
            return {"result": False}
        if settings.verbose:
            logging.debug("%s %s", colored("Found Comparisons:", "magenta"),
                          colored(str(len(smart_contract_comparisons)), "cyan"))
        for smart_contract_comparison in smart_contract_comparisons:
            if settings.verbose:
                logging.debug("%s %s",
                              colored(f"Line {str(smart_contract_comparison['loc']['start']['line'])}:", "magenta"),
                              colored(self._source_unit_explorer.build_node_string(smart_contract_comparison), "cyan"))
            smart_contract_operation_description.append((
                self._source_unit_explorer.get_statement_operand(smart_contract_comparison["left"]).lower(),
                self._source_unit_explorer.get_statement_operand(smart_contract_comparison["right"]).lower(),
                smart_contract_comparison["operator"],
                str(smart_contract_comparison['loc']['start']['line'])))
        for provided_operation in binary_operations:
            operand_1: str = provided_operation["operand_1"].lower()
            operand_2: str = provided_operation["operand_2"].lower()
            operators: list[str] = [provided_operation["operator"],
                                    self._reverse_comparison_operand_map[provided_operation["operator"]]]
            for (smart_contract_operand_1, smart_contract_operand_2,
                 smart_contract_operator, code_line) in smart_contract_operation_description:
                if smart_contract_operator not in operators:
                    continue
                match smart_contract_operator:
                    case "==" | "!=":
                        if (operand_1 in smart_contract_operand_1 and operand_2 in smart_contract_operand_2) \
                                or (operand_2 in smart_contract_operand_1 and operand_1 in smart_contract_operand_2):
                            return {"result": True, "line_match": code_line,
                                    "match_statement": f"{smart_contract_operand_1} {smart_contract_operator} {smart_contract_operand_2}"}
                    case _:
                        if (smart_contract_operator == operators[0]
                            and operand_1 in smart_contract_operand_1
                            and operand_2 in smart_contract_operand_2) \
                                or (smart_contract_operator == operators[1]
                                    and operand_2 in smart_contract_operand_1
                                    and operand_1 in smart_contract_operand_2):
                            return {"result": True, "line_match": code_line,
                                    "match_statement": f"{smart_contract_operand_1} {smart_contract_operator} {smart_contract_operand_2}"}
        return {"result": False}

    def _test_fn_call_check(self, function_calls: list[str], fn_call_statements: list[dict] = None) -> dict[str, bool | str]:
        """
        This function executes the fn_call check: it looks for specific functions call
        :param function_calls: A list of function calls
        :param fn_call_statements: A list of statements to lookup, if omitted all smart-contact's statements will be used
        :return: True if the fn_call check is valid, False otherwise
        """
        if not fn_call_statements:
            fn_call_statements = self._source_unit_explorer.get_all_statements(self._current_smart_contract_definitions,
                                                                               type_filter="FunctionCall")
        smart_contract_function_calls: dict[str, str] = {}
        for fn in fn_call_statements:
            fn_stringfy: str = self._source_unit_explorer.build_node_string(fn).lower()
            if fn_stringfy not in smart_contract_function_calls:
                smart_contract_function_calls[fn_stringfy] = str(fn["loc"]["start"]["line"])
        unique_function_calls: set[str] = set(map(lambda d: d.lower(), function_calls))
        result, trigger = self._compare_literal(search_for=unique_function_calls,
                                                search_in=set(smart_contract_function_calls.keys()))
        if not result:
            return {"result": False}
        else:
            return {"result": True, "line_match": smart_contract_function_calls[trigger], "match_statement": trigger}

    def _test_rejector_check(self) -> dict[str, bool | str]:
        """
        This function executes the rejector check: it looks if the contract implements only a rejection fallback
        :return: True if the rejector check is valid, False otherwise
        """
        smart_contract_functions: list[str] = list(
            self._source_unit_explorer.get_fn_names(self._current_smart_contract_node))
        if len(smart_contract_functions) == 1 \
                and smart_contract_functions[0].lower() == "fallback" \
                and self._current_smart_contract_node.functions["fallback"].isFallback:
            return self._test_fn_call_check(function_calls=["revert(*any*)"])
        return {"result": False}

    def _test_fn_return_parameters_check(self, provided_parameters: list[dict]) -> dict[str, bool | str]:
        """
        This function executes the fn_return_parameters check: it looks if exists a function that returns specific types
        :param provided_parameters: A set of return types
        :return: True if the fn_return_parameters check is valid, False otherwise
        """
        for function in self._current_smart_contract_node.functions:
            function_node: dict = self._current_smart_contract_node.functions[function]._node
            function_return_parameters: list[dict] = self._source_unit_explorer.get_fn_return_parameters(
                fn_node=function_node)
            if self._compare_return_parameters(function_return_parameters, provided_parameters=provided_parameters):
                return {"result": True, "line_match": function_node["loc"]["start"]["line"],
                        "match_statement": function.name}
        return {"result": False}

    def _test_fn_definition_check(self, fn_names: list[str]) -> dict[str, bool | str]:
        """
        This function executes the fn_definition check: it looks for definition of function with a specific name
        :param fn_names: A list of function names
        :return: True if the fn_definition check is valid, False otherwise
        """
        unique_fn_names: set[str] = set(map(lambda d: d.lower(), fn_names))
        smart_contract_fn_names: dict[str, str] = self._source_unit_explorer.get_fn_names(self._current_smart_contract_node)
        result, trigger = self._compare_literal(search_for=unique_fn_names, search_in=set(smart_contract_fn_names.keys()))
        if not result:
            return {"result": False}
        else:
            return {"result": True, "line_match": smart_contract_fn_names[trigger], "match_statement": trigger}

    def _test_event_emit_check(self, event_names: list[str]) -> dict[str, bool | str]:
        """
        This function executes the event_emit check: it looks for definition of event with a specific name
        :param event_names: A list of event names
        :return: True if the event_emit check is valid, False otherwise
        """
        smart_contract_events_names: dict[str, str] = self._source_unit_explorer.get_event_names(
                                                            self._current_smart_contract_node)
        unique_event_names: set[str] = set(map(lambda d: d.lower(), event_names))
        result, trigger = self._compare_literal(search_for=unique_event_names, search_in=set(smart_contract_events_names.keys()))
        if not result:
            return {"result": False}
        else:
            return {"result": True, "line_match": smart_contract_events_names[trigger], "match_statement": trigger}

    def _test_enum_definition_check(self, enum_names: list[str]) -> dict[str, bool | str]:
        """
        This function executes the enum_definition check: it looks for definition of enum with a specific name
        :param enum_names: A list of enum names
        :return: True if the enum_definition check is valid, False otherwise
        """
        smart_contract_enum_names: dict[str, str] = self._source_unit_explorer.get_enum_names(
                                                          self._current_smart_contract_node)
        unique_enum_names = set(map(lambda d: d.lower(), enum_names))
        result, trigger = self._compare_literal(search_for=unique_enum_names, search_in=set(smart_contract_enum_names.keys()))
        if not result:
            return {"result": False}
        else:
            return {"result": True, "line_match": smart_contract_enum_names[trigger], "match_statement": trigger}

    def _test_state_toggle_check(self, state_names: list[str]) -> dict[str, bool | str]:
        """
        This function executes the state_toggle check: it looks for boolean state variable toggles
        :return: True if the state_toggle check is valid, False otherwise
        """
        boolean_states: set[str] = self._source_unit_explorer.get_all_bool_state_vars(self._current_smart_contract_node)
        assignments: dict[str,str] = {}
        for assignment in self._source_unit_explorer.get_all_assignment_statements(
                self._current_smart_contract_definitions, self._assignment_operands):
            assignment_stringfy: str = self._source_unit_explorer.build_node_string(assignment).lower()
            if assignment_stringfy not in assignments:
                assignments[assignment_stringfy] = assignment["loc"]["start"]["line"]
        unique_state_names: set[str] = set(map(lambda d: d.lower(), state_names))
        for boolean_state in boolean_states:
            if self._compare_literal(search_for=unique_state_names, search_in={boolean_state}):
                for assignment_str, assignment_loc in assignments.items():
                    if f"{boolean_state} = !{boolean_state}" == assignment_str:
                        return {"result": True, "line_match": assignment_loc, "match_statement": assignment_str}
        return {"result": False}

    def _test_tight_variable_packing_check(self) -> dict[str, bool | str]:
        """
        This function executes the tight_variable_packing check: it looks for a struct definition which size is <= 32 bytes
        :return: True if the tight_variable_packing check is valid, False otherwise
        """
        for struct_name in self._current_smart_contract_node.structs:
            struct_size: int = 0
            struct_line_code: str = self._current_smart_contract_node.structs[struct_name].loc["start"]["line"]
            members: list[dict] = self._current_smart_contract_node.structs[struct_name]["members"]
            if settings.verbose:
                logging.debug("%s '%s' %s", colored("Found struct:", "magenta"),
                              colored(struct_name, "cyan"), colored(f"at line {struct_line_code}", "magenta"))
            for member in members:
                if (member["typeName"]["type"] != "ElementaryTypeName") or ("fixed" in member["typeName"]["name"]):
                    struct_size = -1
                    break
                else:
                    struct_size += self._source_unit_explorer.get_data_type_byte_size(member["typeName"]["name"])
            if struct_size != -1 and struct_size <= 32:
                return {"result": True, "line_match": struct_line_code, "match_statement": struct_name}
        return {"result": False}

    def _test_memory_array_building_check(self) -> dict[str, bool | str]:
        """
        This function executes the memory_array_building check: it looks a view function with returns a memory array
        :return: True if the memory_array_building check is valid, False otherwise
        """
        for function in self._current_smart_contract_node.functions:
            function_node: dict = self._current_smart_contract_node.functions[function]._node
            if function_node["stateMutability"] == "view" and function_node["returnParameters"]:
                memory_array_parameter: dict = {"storage_location": "memory", "type": "ArrayTypeName"}
                function_parameters: list[dict] = self._source_unit_explorer.get_fn_return_parameters(
                    fn_node=function_node)
                if self._compare_return_parameters(function_parameters, [memory_array_parameter]):
                    return {"result": True, "line_match": function_node["loc"]["start"]["line"],
                            "match_statement": function_node["name"]}
        return {"result": False}

    def _test_check_effects_interaction_check(self) -> dict[str, bool | str]:
        """
        This function executes the check_effects_interaction check: it looks for an assignment before a external fn_call
        :return: True if the check_effects_interaction check is valid, False otherwise
        """
        callable_fn: set[str] = {"send(*any*)", "transfer(*any*)", "call(*any*)"}
        fn_data: dict[str, dict[str, list[int]]] = {}
        for fn_name, fn_statements in self._current_smart_contract_definitions["functions"].items():
            fn_data[fn_name] = {"fn_call_position": [], "assignment_position": []}
            for statement in fn_statements:
                fn_calls: list[dict] = self._source_unit_explorer.find_node_by_type(statement, "FunctionCall")
                assignments: list[dict] = self._source_unit_explorer.find_node_by_type(statement, "BinaryOperation")
                for fn_call in fn_calls:
                    fn_call_string: str = self._source_unit_explorer.build_node_string(fn_call).lower()
                    if self._compare_literal(callable_fn, {fn_call_string}):
                        fn_data[fn_name]["fn_call_position"].append(fn_call["loc"]["start"]["line"])
                for assignment in assignments:
                    if assignment["operator"] in self._assignment_operands:
                        fn_data[fn_name]["assignment_position"].append(assignment["loc"]["start"]["line"])
        for filtered in filter(lambda d: fn_data[d]["fn_call_position"] and fn_data[d]["assignment_position"],
                               fn_data.keys()):
            for assignment_position in fn_data[filtered]["assignment_position"]:
                for fn_call_position in fn_data[filtered]["fn_call_position"]:
                    if (assignment_position + 5) >= fn_call_position:
                        return {"result": True, "line_match": assignment_position, "match_statement": "Check Block"}
        return {"result": False}

    def _test_relay_check(self) -> dict[str, bool | str]:
        """
        This function executes the relay check: it looks if the contract implements a fallback with a delegatecall
        :return: True if the relay check is valid, False otherwise
        """
        relay_fn_call: str = "delegatecall(*any*)"
        smart_contract_functions: list[str] = list(self._source_unit_explorer.get_fn_names(
            self._current_smart_contract_node))
        if "fallback" in smart_contract_functions and self._current_smart_contract_node.functions[
            "fallback"].isFallback:
            fn_call_statements: list[dict] = self._source_unit_explorer.filter_statements_pool(
                statements_pool=self._current_smart_contract_definitions["functions"]["fallback"],
                type_filter="FunctionCall")
            return self._test_fn_call_check(function_calls=[relay_fn_call], fn_call_statements=fn_call_statements)
        return {"result": False}

    def _test_eternal_storage_check(self) -> dict[str, bool | str]:
        """
        This function executes the eternal_storage check: it looks if the contract implements mappings, setter and getter
        :return: True if the eternal_storage check is valid, False otherwise
        """
        smart_contract_mappings: dict[str, dict[str, str]] = self._source_unit_explorer.get_all_mapping_state_vars(
            self._current_smart_contract_node)
        if not smart_contract_mappings:
            return {"result": False}
        smart_contract_fn_names: set[str] = set(self._source_unit_explorer.get_fn_names(self._current_smart_contract_node).keys())
        for mapping_name, mapping_data in smart_contract_mappings.items():
            if mapping_data["visibility"] == "public":
                if f"set{mapping_name}" in smart_contract_fn_names:
                    return {"result": True, "line_match": mapping_data["loc"], "match_statement": mapping_name}
            else:
                if f"set{mapping_name}" in smart_contract_fn_names and f"get{mapping_name}" in smart_contract_fn_names:
                    return {"result": True, "line_match": mapping_data["loc"], "match_statement": mapping_name}
        return {"result": False}

    # === DESCRIBE SMART CONTRACT ===

    def generate_design_pattern_descriptors(self) -> dict[str, list[dict]]:
        """
        This function generates a design pattern descriptors using the generic tests
        :return: A dictionary containing the generated descriptors for each provided smart-contract
        """
        results: dict[str, list[dict]] = {}
        for smart_contract_name in self._visitor.contracts.keys():
            results[smart_contract_name] = self._describe_smart_contract(smart_contract_name=smart_contract_name)
        return results

    def _describe_smart_contract(self, smart_contract_name: str) -> list[dict]:
        """
        This function generate the test's parameters for each generic test
        :param smart_contract_name: The name of the smart contract to describe
        :return: A list of generic tests
        """
        self._current_smart_contract_node = self._visitor.contracts[smart_contract_name]
        self._current_smart_contract_definitions = self._source_unit_explorer.collect_definitions(
            self._current_smart_contract_node)
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
                    test_parameters = set(self._source_unit_explorer.get_base_contract_names(
                        self._current_smart_contract_node).keys())
                    test_keyword = "parent_names"
                case "modifier":
                    test_parameters = set(self._source_unit_explorer.get_modifier_names(
                        self._current_smart_contract_node).keys())
                    test_keyword = "modifiers"
                case "comparison":
                    smart_contract_comparisons = self._source_unit_explorer.get_all_comparison_statements(
                        self._current_smart_contract_definitions, self._reverse_comparison_operand_map)
                    test_parameters = []
                    for comparison in smart_contract_comparisons:
                        test_parameters.append(
                            {
                                "operator": comparison["operator"],
                                "operand_1": self._source_unit_explorer.build_node_string(comparison["left"]),
                                "operand_2": self._source_unit_explorer.build_node_string(comparison["right"])
                            }
                        )
                    test_keyword = "binary_operations"
                case "fn_return_parameters":
                    smart_contract_fn_return_parameters: dict[str, list[dict]] = (
                        self._source_unit_explorer.get_all_fn_return_parameters(self._current_smart_contract_node))
                    test_parameters = []
                    for parameters_list in smart_contract_fn_return_parameters.values():
                        test_parameters += parameters_list
                    test_parameters = [dict(t) for t in {tuple(d.items()) for d in test_parameters}]  # del duplicates
                    test_keyword = "parameters_list"
                case "fn_call":
                    test_parameters = set([self._source_unit_explorer.build_node_string(fn).lower() for fn in
                                           self._source_unit_explorer.get_all_statements(
                                               self._current_smart_contract_definitions, type_filter="FunctionCall")])
                    test_keyword = "callable_function"
                case "fn_definition":
                    test_parameters = set(self._source_unit_explorer.get_fn_names(self._current_smart_contract_node).keys())
                    test_keyword = "fn_names"
                case "event_emit":
                    test_parameters = set(self._source_unit_explorer.get_event_names(self._current_smart_contract_node).keys())
                    test_keyword = "event_names"
                case "enum_definition":
                    test_parameters = set(self._source_unit_explorer.get_enum_names(self._current_smart_contract_node).keys())
                    test_keyword = "enum_names"
                case "state_toggle":
                    test_parameters = self._source_unit_explorer.get_all_bool_state_vars(
                        self._current_smart_contract_node)
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
