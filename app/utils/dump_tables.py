# standalone script to dump tables into jsons/tables

from flask import Flask
from app.models import db

from app.utils.db.util import get_config_option_map, option_selector

from datetime import datetime, date
import argparse
import os
import json

import sys


from app.models import (
    AttackVersion,
    Tactic,
    Technique,
    DataSource,
    DataComponent,
    technique_dc_map,
    technique_ds_map,
    Mismapping,
    CoOccurrence,
    Blurb,
    Platform,
    attack_version_platform_map,
    tactic_platform_map,
    technique_platform_map,
    tactic_technique_map,
    tactic_ds_map,
    Aka,
    technique_aka_map,
    Role,
    User,
)


# Tables / Models
tables = [
    AttackVersion,
    Tactic,
    Technique,
    DataSource,
    DataComponent,
    technique_dc_map,
    technique_ds_map,
    Mismapping,
    CoOccurrence,
    Blurb,
    Platform,
    attack_version_platform_map,
    tactic_platform_map,
    technique_platform_map,
    tactic_technique_map,
    tactic_ds_map,
    Aka,
    technique_aka_map,
    Role,
    User
    # Cart - this is excluded from dump
]


def table_to_dict(table, db):  # Union[Model, Table] -> str (table name), list-of-dicts (table data)

    # this part cannot fail
    if hasattr(table, "__table__"):
        name = table.__table__.name  # Model
    else:
        name = table.name  # Table

    # try getting data, query can fail if a table isn't initialized db-side
    try:

        if hasattr(table, "__table__"):  # Model
            cols = table.__table__.columns.keys()
            rows = table.query.all()
            data = [{col: getattr(row, col) for col in cols} for row in rows]

        else:  # Table
            cols = table.columns.keys()
            rows = db.session.query(table).all()
            data = [{cols[i]: cell for i, cell in enumerate(row)} for row in rows]

    except Exception:
        print(f"Failed to get data for database table {name}. Please ensure it is initialized.")
        data = None

    return name, data


def json_dump_filter(item):
    if isinstance(item, (datetime, date)):
        return item.isoformat()
    return item


def dump_tables(dir, db):
    for table in tables:
        name, data = table_to_dict(table, db)

        # failed to get data -> skip this table
        if data is None:
            print(f"Skipping creation of JSON file for {name}\n")
            continue

        json_path = os.path.join(dir, f"{name}.json")

        print(f'Dumping table "{name}" to {json_path}')
        with open(json_path, "w") as f:
            json.dump(data, f, indent=4, default=json_dump_filter)


def main():

    # optional avenue of command-line instead of text-ui
    parser = argparse.ArgumentParser("Dumps Reports from the DB to a JSON file.")
    parser.add_argument("--config", help="The database configuration to use (from app/conf.py).")
    args = parser.parse_args()

    # perform config selection, can fail on bad cmdline pick
    try:
        app_config = option_selector(
            get_config_option_map(),
            default="DefaultConfig",
            initial_msg="Available app/database configs",
            prompt_msg="Which config to use",
            invalid_msg="is NOT a valid config from",
            cmdline_pick=args.config,
        )
    except Exception as ex:
        print(f"Invalid command-line selection made:\n{ex}")
        sys.exit(1)

    app = Flask(__name__)
    app.config.from_object(app_config)
    db.init_app(app)
    with app.app_context():

        prog_dir = os.path.dirname(os.path.realpath(__file__))
        json_dir = os.path.join(prog_dir, "jsons/tables/")

        dump_tables(json_dir, db)


if __name__ == "__main__":
    main()
