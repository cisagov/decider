from flask import Flask

from app.models import User, db
from app.utils.db.util import app_config_selector

import argparse
import os
import json

import sys


def main():

    # optional avenue of command-line instead of text-ui
    parser = argparse.ArgumentParser("Dumps Users from the DB to a JSON file.")
    parser.add_argument("--config", help="The database configuration to use (from app/conf.py).")
    args = parser.parse_args()

    # perform config selection, can fail on bad cmdline pick
    try:
        app_config = app_config_selector(args.config)
    except Exception as ex:
        print(f"Invalid command-line selection made:\n{ex}")
        sys.exit(1)

    print("\n------------------------------------------------\n")

    app = Flask(__name__)
    app.config.from_object(app_config)
    db.init_app(app)
    with app.app_context():

        # Get user data as list of dicts
        try:
            users = User.query.all()
        except Exception as ex:
            print(f"Failed to get user data from database - due to:\n{ex}")
            sys.exit(2)
        entries = [{"email": u.email, "password": u.password, "role_id": u.role_id} for u in users]

        # Dump to file
        prog_dir = os.path.dirname(os.path.realpath(__file__))
        dump_file = os.path.abspath(os.path.join(prog_dir, "../dumps/user.json"))
        try:
            with open(dump_file, "w") as fhandle:
                json.dump(entries, fhandle, indent=4)
            print(f"Dumped users to {dump_file}!")
        except Exception as ex:
            print(f"Failed to dump users to {dump_file} - due to:\n{ex}")
            sys.exit(3)


if __name__ == "__main__":
    main()
