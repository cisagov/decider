from flask import Flask

from app.models import Cart, db
from app.utils.db.util import app_config_selector
from datetime import datetime, date

import argparse
import os
import json

import sys


def json_dump_defaults(item):

    # time
    if isinstance(item, (datetime, date)):
        return item.isoformat()

    # general
    else:
        return item


def main():

    # optional avenue of command-line instead of text-ui
    parser = argparse.ArgumentParser("Dumps carts from the DB to a JSON file.")
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

        # Get cart data as list of dicts
        try:
            carts = Cart.query.all()
        except Exception as ex:
            print(f"Failed to get cart data from database - due to:\n{ex}")
            sys.exit(2)
        entries = [
            {
                "user": c.user,
                "attack_version": c.attack_version,
                "last_modified": c.last_modified,
                "cart_name": c.cart_name,
                "cart_content": c.cart_content,
            }
            for c in carts
        ]

        # Dump to file
        prog_dir = os.path.dirname(os.path.realpath(__file__))
        dump_file = os.path.abspath(os.path.join(prog_dir, "../dumps/cart.json"))
        try:
            with open(dump_file, "w") as fhandle:
                json.dump(entries, fhandle, indent=4, default=json_dump_defaults)
            print(f"Dumped carts to {dump_file}!")
        except Exception as ex:
            print(f"Failed to dump carts to {dump_file} - due to:\n{ex}")
            sys.exit(3)


if __name__ == "__main__":
    main()
