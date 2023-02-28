from flask import Flask

from app.models import Mismapping, db
import app.utils.db.read as db_read
from app.utils.db.util import option_selector, app_config_selector

import argparse
import os
import json

import sys


def main():

    # optional avenue of command-line instead of text-ui
    parser = argparse.ArgumentParser("Dumps Mismappings from the DB to a JSON file.")
    parser.add_argument("--config", help="The database configuration to use (from app/conf.py).")
    parser.add_argument("--version", help="ATT&CK version for mismapping content to be dumped from.")
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

        # Determine existing content
        try:
            versions_installed = set(db_read.attack.versions())
        except Exception as ex:
            print(f"Failed to read what ATT&CK versions are currently installed on the DB - due to:\n{ex}")
            sys.exit(3)
        if len(versions_installed) == 0:
            print("There are no versions to dump mismapping content from. Exiting.")
            return

        # Allow user to select a version to dump from
        try:
            to_dump = option_selector(
                versions_installed,
                initial_msg="ATT&CK versions on the database",
                prompt_msg="What version to dump content from",
                invalid_msg="is NOT a valid version from",
                cmdline_pick=args.version,
            )
        except Exception as ex:
            print(f"Invalid command-line selection made:\n{ex}")
            sys.exit(4)

        # Read Technique data into map that resolves DB Unique ID to Technique IDs
        try:
            tech_uid_to_id = {tuid: tid for tid, tuid in db_read.attack.tech_id_to_uid(to_dump).items()}
        except Exception as ex:
            print(f"Failed to read information about Techniques present in the DB - due to:\n{ex}")
            sys.exit(5)

        # Get mismapping data as list of dicts
        try:
            mismapings = db.session.query(Mismapping).filter(Mismapping.original.in_(tech_uid_to_id.keys())).all()
        except Exception as ex:
            print(f"Failed to get mismapping data from database - due to:\n{ex}")
            sys.exit(6)
        entries = [
            {
                "original": tech_uid_to_id[m.original],  # always defined
                "corrected": tech_uid_to_id.get(m.corrected, "N/A"),  # might be undefined
                "context": m.context,
                "rationale": m.rationale,
            }
            for m in mismapings
        ]
        entries.sort(key=lambda mm: f"{mm['original']}{mm['corrected']}{mm['context']}{mm['rationale']}")

        # Dump to file
        prog_dir = os.path.dirname(os.path.realpath(__file__))
        dump_file = os.path.abspath(os.path.join(prog_dir, f"../dumps/mismappings-{to_dump}.json"))
        try:
            with open(dump_file, "w") as fhandle:
                json.dump(entries, fhandle, indent=4)
            print(f"Dumped mismappings to {dump_file}!")
        except Exception as ex:
            print(f"Failed to dump mismappings to {dump_file} - due to:\n{ex}")
            sys.exit(7)


if __name__ == "__main__":
    main()
