from flask import Flask

from app.models import db

import app.utils.db.read as db_read
import app.utils.db.destroy as db_destroy
from app.utils.db.util import option_selector, app_config_selector

import argparse
import time

import sys

# ---------------------------------------------------------------------------------------------------------------------


def main():

    # optional avenue of command-line instead of text-ui
    parser = argparse.ArgumentParser("Removes an ATT&CK version from the database.")
    parser.add_argument("--config", help="The database configuration to use (from app/conf.py).")
    parser.add_argument("--version", help="ATT&CK version to be removed.")
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

        # DB ASSESSMENT + SELECTION -----------------------------------------------------------------------------------

        # Determine existing content
        try:
            versions_installed = set(db_read.attack.versions())
        except Exception as ex:
            print(f"Failed to read what ATT&CK versions are currently installed on the DB - due to:\n{ex}")
            sys.exit(3)
        if len(versions_installed) == 0:
            print("There are no versions to remove. Exiting.")
            return

        # Allow user to select a version to remove
        try:
            to_remove = option_selector(
                versions_installed,
                initial_msg="Versions installed on the database",
                prompt_msg="What version to remove",
                invalid_msg="is NOT a valid version from",
                cmdline_pick=args.version,
            )
        except Exception as ex:
            print(f"Invalid command-line selection made:\n{ex}")
            sys.exit(4)

        # Get details of if version had CoOcs, AKAs, Mismaps to remove as well
        try:
            has_co_ocs = db_read.coocs.exists_for_version(to_remove)
            has_akas = db_read.akas.exists_for_version(to_remove)
            has_mismaps = db_read.mismaps.exists_for_version(to_remove)
        except Exception as ex:
            print(
                "Failed to assess if optional content (Co-ocs, AKAs, Mismaps)"
                f" existed for version {to_remove} - due to:\n{ex}"
            )
            sys.exit(5)

        print("\n------------------------------------------------\n")

        # REMOVAL INFO PRINT-OUT --------------------------------------------------------------------------------------

        print("Removal Detail:")
        print(f" - ATT&CK Version {to_remove}:")
        if has_co_ocs:
            print("    - CoOccurrences")
        if has_akas:
            print("    - AKAs")
        if has_mismaps:
            print("    - Mismappings")

        print("\n------------------------------------------------\n")

        # TEAR DOWN PROCESS -------------------------------------------------------------------------------------------

        t0 = time.time()

        # ATT&CK + Tree content
        try:
            db_destroy.attack.drop_version(to_remove)
        except Exception as ex:
            tfail = time.time() - t0
            print(
                f"Failed to remove ATT&CK/Tree content for version {to_remove}"
                f" at {tfail:.1f}s into build - due to:\n{ex}"
            )
            sys.exit(6)

        print("\n------------------------------------------------\n")
        tdone = time.time() - t0
        print(f"SUCCESS - Removed Version {to_remove} In: {tdone:.1f}s!")


if __name__ == "__main__":
    main()
