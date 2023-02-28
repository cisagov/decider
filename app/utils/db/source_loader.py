from abc import ABC, abstractmethod

import json
import os
import re

import functools

open_utf8 = functools.partial(open, encoding="UTF-8")  # ensures windows is working in UTF-8 mode as well


class SourceFile(ABC):
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.exists = os.path.isfile(path)  # used by manager to handle available sources
        self.loaded = False
        self.data = None

    def load(self):
        # raise Exception if issue loading (/no need to 'try' here)
        with open_utf8(self.path) as fhandle:
            self.data = json.load(fhandle)

    @abstractmethod
    def validate(self):
        # ensure data assumptions
        # can post-process as well
        # raise Exception if issue in format
        pass

    def load_validate(self):
        class_name = type(self).__name__

        # doesn't exist -> fail
        if not self.exists:
            print(f"Loading {class_name} at {self.path} failed as it does not exist!")
            return False

        # attempt load
        try:
            self.load()
        except Exception as ex:
            print(f"Loading {class_name} at {self.path} failed due to:\n{ex}")
            return False

        # attempt validation
        try:
            self.validate()
        except Exception as ex:
            print(f"Validating {class_name} at {self.path} failed due to:\n{ex}")
            return False

        # success
        self.loaded = True
        return True

    # must be try excepted first time - if success,
    def get_data(self):
        if self.loaded:
            return self.data


class AttackFile(SourceFile):
    def validate(self):
        """Validates loaded JSON structure & builds STIX ID index for active items"""
        data = self.data

        # need {}
        if not isinstance(data, dict):
            raise Exception(f"ATT&CK file root isn't dict as expected - it's a {type(data).__name__}")

        # need { "type": "bundle" }
        if data.get("type") != "bundle":
            raise Exception("ATT&CK file root isn't marked as type=bundle")

        # need { "type": "bundle", "objects": [ ... ] }
        items = data.get("objects")
        if (not isinstance(items, list)) or (len(items) == 0):
            raise Exception("ATT&CK file root 'objects' field missing, empty, or not a list")

        # filter out dep/revoked objects
        active_primary = {
            item["id"]: item
            for item in items
            if not item.get("x_mitre_deprecated", False) and not item.get("revoked", False)
        }

        # filter out dep/revoked relationships
        active_secondary = {
            item_id: item
            for item_id, item in active_primary.items()
            if item["type"] != "relationship"
            or (item["source_ref"] in active_primary and item["target_ref"] in active_primary)
        }

        # need 1 matrix exactly
        matrix_ids = [item_id for item_id, item in active_secondary.items() if item["type"] == "x-mitre-matrix"]
        if len(matrix_ids) != 1:
            raise Exception(f"ATT&CK file has {len(matrix_ids)} Matrices - exactly 1 required for Enterprise")

        # need 1+ tactics
        tactic_ids = [item_id for item_id, item in active_secondary.items() if item["type"] == "x-mitre-tactic"]
        if len(tactic_ids) == 0:
            raise Exception("ATT&CK file has 0 Tactics")

        # need 1+ techniques
        technique_ids = [item_id for item_id, item in active_secondary.items() if item["type"] == "attack-pattern"]
        if len(technique_ids) == 0:
            raise Exception("ATT&CK file has 0 Techniques")

        self.data = active_secondary


class TreeFile(SourceFile):
    def validate(self):

        # base object is dictionary
        if not isinstance(self.data, dict):
            raise Exception("The root of this file isn' a dictionary as expected.")

        # check entries
        for ind, (key, value) in enumerate(self.data.items()):

            # keys are Tactic / (Sub)Technique IDs
            if not isinstance(key, str):
                raise Exception(f"The key ({key}) for entry #{ind} is not a string as expected.")
            if not (re.fullmatch(r"TA[0-9]{4}", key) or re.fullmatch(r"T[0-9]{4}(\.[0-9]{3})?", key)):
                raise Exception(f"The key ({key}) for entry #{ind} is not a Technique/Tactic ID as expected.")

            # values are dictionaries with required keys
            if not isinstance(value, dict):
                raise Exception(f"The value at key ({key}) is not a dictionary as expected.")

            expected_keys = {"question", "answer"}
            if not expected_keys.issubset(value.keys()):
                raise Exception(f"The entry at key ({key}) does not have all required keys: {expected_keys}.")


class RoleFile(SourceFile):
    def validate(self):

        # base object is list
        if not isinstance(self.data, list):
            raise Exception("This root of this file is not a list as expected.")

        # check entries
        for ind, entry in enumerate(self.data):

            # entries are dictionaries with required keys
            if not isinstance(entry, dict):
                raise Exception(f"Entry #{ind} is not a dictionary as expected.")
            expected_keys = {"role_id", "name", "description"}
            if not expected_keys.issubset(entry.keys()):
                raise Exception(f"Entry #{ind} does not have all required keys: {expected_keys}.")


class UserFile(SourceFile):
    def validate(self):

        # base object is list
        if not isinstance(self.data, list):
            raise Exception("Root of this file is not a list as expected.")

        # check entries
        for ind, entry in enumerate(self.data):

            # entries are dictionaries with required keys
            if not isinstance(entry, dict):
                raise Exception(f"Entry #{ind} is not a dictionary as expected.")
            expected_keys = {"email", "password", "role_id"}
            if not expected_keys.issubset(entry.keys()):
                raise Exception(f"Entry #{ind} does not have all required keys: {expected_keys}.")


class CartFile(SourceFile):
    def validate(self):

        # base object is list
        if not isinstance(self.data, list):
            raise Exception("The root of this file is not a list as expected.")

        # check entries
        for ind, entry in enumerate(self.data):

            # entries are dictionaries with required keys
            if not isinstance(entry, dict):
                raise Exception(f"Entry #{ind} is not a dictionary as expected.")
            expected_keys = {
                "user",
                "attack_version",
                "last_modified",
                "cart_name",
                "cart_content",
            }
            if not expected_keys.issubset(entry.keys()):
                raise Exception(f"Entry #{ind} does not have all required keys: {expected_keys}.")


class CoOccurrencesFile(SourceFile):
    def validate(self):

        # base object is list
        if not isinstance(self.data, list):
            raise Exception("Root of this file is not a list as expected.")

        # check entries
        for ind, entry in enumerate(self.data):

            # entries are dictionaries with required keys
            if not isinstance(entry, dict):
                raise Exception(f"Entry #{ind} is not a dictionary as expected.")
            expected_keys = {
                "technique_i",
                "technique_j",
                "score",
                "i_references",
                "j_references",
                "shared_references",
                "shared_percent",
                "j_avg",
                "j_std",
            }
            if not expected_keys.issubset(entry.keys()):
                raise Exception(f"Entry #{ind} does not have all required keys: {expected_keys}.")


class MismappingsFile(SourceFile):
    def validate(self):

        # base object is list
        if not isinstance(self.data, list):
            raise Exception("Root of this file is not a list as expected.")

        # check entries
        for ind, entry in enumerate(self.data):

            # entries are dictionaries with required keys
            if not isinstance(entry, dict):
                raise Exception(f"Entry #{ind} is not a dict as expected.")
            expected_keys = {"original", "corrected", "context", "rationale"}
            if not expected_keys.issubset(entry.keys()):
                raise Exception(f"Entry #{ind} does not have all required keys: {expected_keys}.")


class AkasFile(SourceFile):
    def validate(self):

        # base object is list
        if not isinstance(self.data, list):
            raise Exception("Root of this file is not a list as expected.")

        # check entries
        for ind, entry in enumerate(self.data):

            # entries are dictionaries with required keys
            if not isinstance(entry, dict):
                raise Exception(f"Entry #{ind} is not a dictionary as expected.")
            expected_keys = {"id", "akas"}
            if not expected_keys.issubset(entry.keys()):
                raise Exception(f"Entry #{ind} does not have all required keys: {expected_keys}.")


class SourceManager:
    @staticmethod
    def multiversion_as_dict(clas, dirpath):
        # takes a folder of source files with versions markers and creates
        #   a dictionary mapping each verion marker to its source file
        # filenames are expected in the form: name-vN.N.json
        # filenames can contain additional dashes: multipart-name-vN.N.json
        # filenames must have at least 1 dash
        #   the dash is used to grab the version of the file
        #   name-{version is between the last dash and the extension}.json

        instances = {}

        if os.path.isdir(dirpath):
            folder_items = [os.path.join(dirpath, item) for item in os.listdir(dirpath)]
            folder_files = [item for item in folder_items if os.path.isfile(item)]
            folder_jsons = [file for file in folder_files if file.endswith(".json")]
            for json_path in folder_jsons:
                base_name = os.path.basename(json_path)
                base_name_extless = base_name[: -len(".json")]
                if "-" not in base_name_extless:
                    continue
                version = base_name_extless.split("-")[-1]  # 'co-occurrences-(v8.0)'
                instances[version] = clas(json_path)

        return instances

    def __init__(self, sources_dir):
        self.role = RoleFile(os.path.join(sources_dir, "./role.json"))
        self.user = UserFile(os.path.join(sources_dir, "./user.json"))
        self.cart = CartFile(os.path.join(sources_dir, "./cart.json"))
        self.attack = self.multiversion_as_dict(AttackFile, os.path.join(sources_dir, "./enterprise-attack/"))
        self.tree = self.multiversion_as_dict(TreeFile, os.path.join(sources_dir, "./tree/"))
        self.co_ocs = self.multiversion_as_dict(CoOccurrencesFile, os.path.join(sources_dir, "./co_occurrences/"))
        self.mismaps = self.multiversion_as_dict(MismappingsFile, os.path.join(sources_dir, "./mismappings/"))
        self.akas = self.multiversion_as_dict(AkasFile, os.path.join(sources_dir, "./akas/"))
