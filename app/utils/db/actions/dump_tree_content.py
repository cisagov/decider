from flask import Flask

from app.models import Tactic, Technique, db
import app.utils.db.read as db_read
from app.utils.db.util import option_selector, app_config_selector

import argparse
import os
import json
import itertools

import sys


def score_attack_id(id_):
    # Used as a scoring function for ATT&CK ID strings
    # Tactics in Matrix order - these come first
    # Techniques in ascending number order

    # Tactic: position(TAwxyz) - 1,000.0
    if id_.startswith("TA"):

        # get Matrix order - fail to 100 if more Tactics exist
        inter_tactic_order = [
            "TA0043",
            "TA0042",
            "TA0001",
            "TA0002",
            "TA0003",
            "TA0004",
            "TA0005",
            "TA0006",
            "TA0007",
            "TA0008",
            "TA0009",
            "TA0011",
            "TA0010",
            "TA0040",
        ]
        try:
            pos = inter_tactic_order.index(id_)
        except ValueError:
            pos = 100
        return pos - 1_000.0

    # Technique: T(wxyz.abc)
    else:
        return float(id_[1:])


# ---------------------------------------------------------------------------------------------------------------------


def main():

    # optional avenue of command-line instead of text-ui
    parser = argparse.ArgumentParser(
        "Dumps the question/answer card content for an ATT&CK version from the DB to a JSON file."
    )
    parser.add_argument("--config", help="The database configuration to use (from app/conf.py).")
    parser.add_argument("--version", help="ATT&CK version for card content to be dumped from.")
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
            print("There are no versions to dump tree content from. Exiting.")
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

        # Get Tactic & Technique question/answer content (+ names for human convenience)
        try:
            tact_id_nqa = (
                db.session.query(
                    Tactic.tact_id,
                    Tactic.tact_name,
                    Tactic.tact_question,
                    Tactic.tact_answer,
                ).filter(Tactic.attack_version == to_dump)
            ).all()

            tech_id_nqa = (
                db.session.query(
                    Technique.tech_id,
                    Technique.tech_name,
                    Technique.tech_question,
                    Technique.tech_answer,
                ).filter(Technique.attack_version == to_dump)
            ).all()
        except Exception as ex:
            print(f"Failed to read Tactic & Technique Question/Answer content from DB - due to\n:{ex}")
            sys.exit(5)

        # Order Tactics Matrix-wise, Place Techniques after ascending ID number-wise, make into dict
        entries = [
            {"id": row[0], "__name": row[1], "question": row[2], "answer": row[3]}
            for row in itertools.chain(tact_id_nqa, tech_id_nqa)
        ]
        entries.sort(key=lambda entry: score_attack_id(entry["id"]))
        entries = {
            e["id"]: {
                "__name": e["__name"],
                "question": e["question"],
                "answer": e["answer"],
            }
            for e in entries
        }

        # Dump to file
        prog_dir = os.path.dirname(os.path.realpath(__file__))
        dump_file = os.path.abspath(os.path.join(prog_dir, f"../dumps/tree-content-{to_dump}.json"))
        try:
            with open(dump_file, "w") as fhandle:
                json.dump(entries, fhandle, indent=4)
            print(f"Dumped tree content for version {to_dump} to {dump_file}!")
        except Exception as ex:
            print(f"Failed to dump tree content to {dump_file} - due to:\n{ex}")
            sys.exit(6)


if __name__ == "__main__":
    main()
