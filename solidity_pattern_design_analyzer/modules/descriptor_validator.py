import json
import logging
from json import JSONDecodeError
from pathlib import Path
from typing import IO

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
                logging.debug(colored("Parsing schema: '{}' ...".format(schema_path), "blue"))
            schema_fp: IO = open(schema_path, "r")
            self._descriptor_schema = json.load(schema_fp)
            schema_fp.close()
        except OSError as fp_error:
            error = "An error occurred while trying to open the file '{}', aborting...\n{}" \
                .format(schema_path, fp_error)
        except JSONDecodeError as json_error:
            error = "An error occurred while trying to parse the json content of '{}', aborting...\n{}" \
                .format(schema_path, json_error.msg)
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
        descriptors: list[dict] = list()
        for descriptor_path in descriptors_path:
            error: str = ""
            try:
                if settings.verbose:
                    logging.debug(colored("Checking descriptor: '{}' ...".format(descriptor_path), "blue"))
                descriptor_fp: IO = open(descriptor_path, "r")
                descriptor_object = json.load(descriptor_fp)
                descriptor_fp.close()
                validate(instance=descriptor_object, schema=self._descriptor_schema)
                if settings.verbose:
                    logging.debug(colored("{} - Descriptor has been deserialized and validated successfully!"
                                          .format(descriptor_object["name"]), "green"))
                descriptors.append(descriptor_object)
            except OSError as fp_error:
                error = "An error occurred while trying to open the file '{}', skipping...\n{}" \
                    .format(descriptor_path, fp_error)
            except JSONDecodeError as json_error:
                error = "An error occurred while trying to parse the json content of '{}', skipping...\n{}" \
                    .format(descriptor_path, json_error.msg)
            except SchemaError as schema_error:
                logging.error(colored("The provided descriptor schema is not valid, please check compliance with "
                                      "Draft-07, aborting...\n{}".format(schema_error.message), "red"))
                break
            except ValidationError as validation_error:
                error = "The descriptor '{}' is not valid, skipping...\n{}"\
                    .format(descriptor_path, validation_error.message)
            finally:
                if error:
                    logging.error(colored(error, "red"))
        return descriptors
