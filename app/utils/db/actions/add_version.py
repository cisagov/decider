from flask import Flask

from app.models import db

from app.utils.db.source_loader import SourceManager
from app.utils.db.util import option_selector, app_config_selector
import app.utils.db.read as db_read
import app.utils.db.create as db_create

import argparse
import os
import time

import sys

# ---------------------------------------------------------------------------------------------------------------------


def main():

    # optional avenue of command-line instead of text-ui
    parser = argparse.ArgumentParser("Adds a new ATT&CK version to the DB from the local disk.")
    parser.add_argument("--config", help="The database configuration to use (from app/conf.py).")
    parser.add_argument("--version", help="ATT&CK version to be added.")
    args = parser.parse_args()

    # ensure all-or-nothing command-line argument pick
    if len([a for a in (args.config, args.version) if a is not None]) not in [0, 2]:
        print("Either ALL or NONE of the command-line args should be defined. Exiting.")
        sys.exit(1)

    # perform config selection, can fail on bad cmdline pick
    try:
        app_config = app_config_selector(args.config)
    except Exception as ex:
        print(f"Invalid command-line selection made:\n{ex}")
        sys.exit(2)

    print("\n------------------------------------------------\n")

    app = Flask(__name__)
    app.config.from_object(app_config)
    db.init_app(app)
    with app.app_context():

        # RESOURCE LOADING --------------------------------------------------------------------------------------------

        utils_dir = os.path.dirname(os.path.realpath(__file__))
        sources_dir = os.path.join(utils_dir, "../../jsons/source/")
        src_mgr = SourceManager(sources_dir)

        # Determine existing content
        try:
            versions_installed = set(db_read.attack.versions())
        except Exception as ex:
            print(f"Failed to read what ATT&CK content is currently installed in the DB - due to:\n{ex}")
            sys.exit(3)
        print(f"Currently Installed: {sorted(list(versions_installed))}\n")

        # Determine content that can be added
        disk_versions = set(src_mgr.attack.keys())  # installables need ATT&CK content
        disk_versions = disk_versions.intersection(set(src_mgr.tree.keys()))  # installables need Tree content
        print(f"Available on Disk: {sorted(list(disk_versions))}")
        installable_versions = disk_versions.difference(
            versions_installed
        )  # installables must not already be installed

        if len(installable_versions) == 0:
            print("There are no versions that can be installed!")
            return

        # Allow user to select a version to install
        try:
            to_install = option_selector(
                installable_versions,
                initial_msg="Versions on-disk but not on-DB",
                prompt_msg="What version to install",
                invalid_msg="is NOT a valid version from",
                cmdline_pick=args.version,
            )
        except Exception as ex:
            print(f"Invalid command-line selection made:\n{ex}")
            sys.exit(4)

        print("\n------------------------------------------------\n")

        # Load ATT&CK
        if src_mgr.attack[to_install].load_validate():
            print("Loaded ATT&CK content.")
        else:
            print("Failed to load ATT&CK content. Exiting.")
            sys.exit(5)

        print("\n------------------------------------------------\n")

        # Load Tree
        if src_mgr.tree[to_install].load_validate():
            print("Loaded Tree content (questions / answers).")
        else:
            print("Failed to load Tree content (questions / answers). Exiting")
            sys.exit(6)

        print("\n------------------------------------------------\n")

        # Load AKAs if available
        akas_loaded = False
        if to_install in src_mgr.akas.keys():
            print("Located AKAs, attempting to load and include in install.")
            if src_mgr.akas[to_install].load_validate():
                print("AKAs loaded!")
                akas_loaded = True
            else:
                print("Failed to load AKAs. Skipping for this install.")

        print("\n------------------------------------------------\n")

        # Load CoOccurences if available
        co_ocs_loaded = False
        if to_install in src_mgr.co_ocs.keys():
            print("Located CoOccurrences, attempting to load and include in install.")
            if src_mgr.co_ocs[to_install].load_validate():
                print("CoOccurrences loaded!")
                co_ocs_loaded = True
            else:
                print("Failed to load CoOccurrences. Skipping for this install.")

        print("\n------------------------------------------------\n")

        # Load Mismappings if available
        mismaps_loaded = False
        if to_install in src_mgr.mismaps.keys():
            print("Located Mismappings, attempting to load and include in install.")
            if src_mgr.mismaps[to_install].load_validate():
                print("Mismappings loaded!")
                mismaps_loaded = True
            else:
                print("Failed to load Mismappings. Skipping for this install.")

        print("\n------------------------------------------------\n")

        # INSTALL INFO PRINT-OUT --------------------------------------------------------------------------------------

        print("Install Detail:")
        print(f" + ATT&CK Version {to_install}:")
        if co_ocs_loaded:
            print("    + CoOccurrences")
        if akas_loaded:
            print("    + AKAs")
        if mismaps_loaded:
            print("    + Mismappings")

        print("\n------------------------------------------------\n")

        # BUILDING PROCESS --------------------------------------------------------------------------------------------

        t0 = time.time()

        # ATT&CK + Tree content
        try:
            db_create.attack.add_version(to_install, src_mgr)
        except Exception as ex:
            tfail = time.time() - t0
            print(
                f"Failed to add ATT&CK/Tree content for version {to_install}"
                f" at {tfail:.1f}s into build - due to:\n{ex}"
            )
            sys.exit(7)

        # AKAs
        if akas_loaded:
            try:
                db_create.akas.add_version(to_install, src_mgr)
            except Exception as ex:
                tfail = time.time() - t0
                print(f"Failed to add AKAs for version {to_install} at {tfail:.1f}s into build - due to:\n{ex}")
                sys.exit(8)

        # CoOccurrences
        if co_ocs_loaded:
            try:
                db_create.coocs.add_version(to_install, src_mgr)
            except Exception as ex:
                tfail = time.time() - t0
                print(
                    f"Failed to add ATT&CK/Tree content for version {to_install}"
                    f" at {tfail:.1f}s into build - due to:\n{ex}"
                )
                sys.exit(9)

        # Mismappings
        if mismaps_loaded:
            try:
                db_create.mismaps.add_version(to_install, src_mgr)
            except Exception as ex:
                tfail = time.time() - t0
                print(
                    f"Failed to add ATT&CK/Tree content for version {to_install}"
                    f" at {tfail:.1f}s into build - due to:\n{ex}"
                )
                sys.exit(10)

        print("\n------------------------------------------------\n")
        tdone = time.time() - t0
        print(f"SUCCESS - Added Version {to_install} In: {tdone:.1f}s!")


if __name__ == "__main__":
    main()
