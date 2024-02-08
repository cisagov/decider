from textwrap import dedent as txt_dedent
import bcrypt
import json
import os
from app.utils.db.saltstack_scram_sha_256 import scram_sha_256
from app.env_vars import (
    # app database
    DB_DATABASE,
    # db admin user
    DB_ADMIN_NAME,
    DB_ADMIN_PASS,
    # app admin login
    APP_ADMIN_EMAIL,
    APP_ADMIN_PASS,
)

init_sql_template = txt_dedent(
    """
    -- Flask Connection / Only User
    CREATE ROLE {db_admin_name} WITH CREATEROLE LOGIN PASSWORD '{db_admin_pass}';
    CREATE DATABASE {db_database};
    \\c {db_database};
    GRANT ALL PRIVILEGES ON DATABASE {db_database} to {db_admin_name};
    """
)

introduction_text = txt_dedent(
    """
    This script reads your .env file as input!

    This script creates
    -------------------
    - init.sql  (in decider root)
    > creates DB 'decider' (DB_DATABASE), DB user, and sets-up needed functionality.

    - user.json (in config/build_sources)
    > an entry for a Decider Admin is created, so it is usable after build.

    Next Steps
    ----------
    1. init.sql is used to create a database, user, and enable extensions
    2. full_build.py creates and populates DB tables, creating a login for the new user.json as well

    NOTICE
    ------
    This script is only allowed to create files.
    It will exit on attempted overwrite.
    This is a safety precaution (not normal to need this step multiple times).
    Manually delete the files if you need and start over :)
    """
)


def decider_rel_to_abs_path(rel_path):
    decider_root = os.path.dirname(os.path.realpath(__file__))
    abs_path = os.path.abspath(os.path.join(decider_root, rel_path))
    return abs_path


def main():
    # -----------------------------------------------------------------------------------------------------------------
    # welcome

    print(introduction_text)

    # -----------------------------------------------------------------------------------------------------------------
    # write 'init.sql'

    init_sql_p = decider_rel_to_abs_path("./init.sql")

    print("Creating init.sql...  ", end="")

    with open(init_sql_p, "xt") as sql_file:
        sql_file.write(
            init_sql_template.format(
                db_database=DB_DATABASE,
                db_admin_name=DB_ADMIN_NAME,
                db_admin_pass=scram_sha_256(password=DB_ADMIN_PASS),
            )
        )

    print("done!")

    # -----------------------------------------------------------------------------------------------------------------
    # write 'user.json'

    user_json_p = decider_rel_to_abs_path("config/build_sources/user.json")

    # add entry with hashed password
    print("Creating user.json... ", end="")

    user_json_content = [
        {
            "email": APP_ADMIN_EMAIL,
            "password": bcrypt.hashpw(APP_ADMIN_PASS.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            "role_id": 3,
        }
    ]

    with open(user_json_p, "xt") as user_json:
        json.dump(user_json_content, user_json, indent=4)

    print("done!")
    # -----------------------------------------------------------------------------------------------------------------


if __name__ == "__main__":
    main()
