import json
import logging
from json import JSONDecodeError
from pathlib import Path

from jsonschema import validate, SchemaError, ValidationError
from termcolor import colored

from modules.config import settings


class DescriptorValidator:
    _descriptor_path: str
    _descriptor_schema: dict

    def __init__(self, descriptor_path: str) -> None:
        self._descriptors_path = Path(descriptor_path)

    def load_schema(self, schema_path: str) -> bool:
        """
        This function parses and stores the provided json schema
        :param schema_path: A valid json schema path
        :return: True if the schema is successfully parsed, False otherwise
        """
        error: str = ""
        try:
            if settings.verbose:
                logging.debug("%s '%s'", colored(f"Parsing schema:", "blue"), colored(schema_path, "cyan"))
            with open(schema_path, "r") as schema_fp:
                self._descriptor_schema = json.load(schema_fp)
        except OSError as fp_error:
            error = f"An error occurred while trying to open the file '{schema_path}', aborting...\n{fp_error}"
        except JSONDecodeError as json_error:
            error = f"An error occurred while trying to parse the json content of '{schema_path}', aborting...\n{json_error.msg} "
        finally:
            if not error:
                if settings.verbose:
                    logging.debug(colored("The provided schema has been parsed successfully!", "green"))
                return True
            else:
                logging.error(colored(error, "red"))
                return False

    def _get_available_descriptors(self) -> list[Path]:
        """
        This function looks for descriptors files on the provided path
        :return: A list of file's path
        """
        files: list[Path] = list()
        if self._descriptors_path.is_file():
            files.append(self._descriptors_path)
        else:
            for file in self._descriptors_path.glob("**/*.json"):
                files.append(Path(file))
        return files

    def load_descriptors(self) -> list[dict]:
        """
        This function parses, validate and stores the provided descriptors
        :return: A list of validated descriptors
        """
        if not self._descriptor_schema:
            logging.error(colored("Unable to load descriptors without a loaded descriptor schema", "red"))
            return []
        descriptors_path: list[Path] = self._get_available_descriptors()
        descriptors: list[dict] = []
        for descriptor_path in descriptors_path:
            error: str = ""
            try:
                if settings.verbose:
                    logging.debug("%s '%s'", colored(f"Checking descriptor:", "blue"),
                                                   colored(str(descriptor_path), "cyan"))
                with open(descriptor_path, "r") as descriptor_fp:
                    descriptor_object = json.load(descriptor_fp)
                validate(instance=descriptor_object, schema=self._descriptor_schema)
                if settings.verbose:
                    logging.debug("%s %s", colored(descriptor_object['name'], "cyan"),
                                                 colored("- Descriptor has been deserialized and "
                                                         "validated successfully!", "green"))
                descriptors.append(descriptor_object)
            except OSError as fp_error:
                error = f"An error occurred while trying to open the file '{descriptor_path}', skipping...\n{fp_error}"
            except JSONDecodeError as json_error:
                error = f"An error occurred while trying to parse the json content of '{descriptor_path}', skipping...\n{json_error.msg}"
            except SchemaError as schema_error:
                logging.error(colored("The provided descriptor schema is not valid, please check compliance with "
                                      f"Draft-07, aborting...\n{schema_error.message}", "red"))
                break
            except ValidationError as validation_error:
                error = f"The descriptor '{descriptor_path}' is not valid, skipping...\n{validation_error.message}"
            finally:
                if error:
                    logging.error(colored(error, "red"))
        return descriptors
