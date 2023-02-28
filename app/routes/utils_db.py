"""
This variant of utils may import from app.models / use app variables
Check out utils.py for why the separation exists
"""

from app.models import AttackVersion

from flask import jsonify, g
from flask_login import current_user

import logging

logger = logging.getLogger(__name__)


class VersionPicker:
    """Populates global Jinja vars with the current/available versions, provides program with current selected version

    'The overall ATT&CK catalog is versioned using a major.minor version schema.'
    - https://attack.mitre.org/resources/versions/

    So, AttackVersion's version column str is of the format: v{int}.{int} (which is also v{float})
    """

    def __init__(self, version=None):
        logger.debug("VersionPicker querying available ATT&CK versions")

        ver_str_to_model = {av.version: av for av in AttackVersion.query.all()}
        self.all_versions = sorted(
            list(ver_str_to_model.keys()),
            key=lambda ver_str: float(ver_str.replace("v", "")),
        )

        # no versions installed
        if len(self.all_versions) == 0:
            self.is_valid = False
            self.cur_version = None
            logger.critical("!!! No versions of ATT&CK are installed on the server !!!".upper())

        # specified externally (by URL), can be invalid
        elif version:
            self.is_valid = version in self.all_versions
            self.cur_version = version

        # user-derived, always valid
        else:
            self.is_valid = True

            # version saved -> use that
            if current_user.last_attack_ver:
                self.cur_version = current_user.last_attack_ver

            # no version saved -> most recent version default
            else:
                self.cur_version = self.all_versions[-1]

        # provides reference to model if defined - saves
        # an extra query when getting platforms / tactics
        self.cur_version_model = ver_str_to_model[self.cur_version] if self.is_valid else None

    def set_vars(self):
        # sets global version variables if version is valid; returns if setting was done or not

        if self.is_valid:
            g.version_picker = {
                "all_versions": self.all_versions,
                "cur_version": self.cur_version,
                "cur_version_float": float(self.cur_version.replace("v", "")),
            }
        return self.is_valid

    def get_invalid_message(self):
        return jsonify(message="The value for version is not a valid version."), 404
