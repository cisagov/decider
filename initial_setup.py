import bcrypt
import json
import os
import hashlib
from app.env_vars import ADMIN_EMAIL, ADMIN_PASS, DB_USERNAME, DB_PASSWORD, DB_DATABASE

init_sql_template = """\
-- Flask Connection / Only User
CREATE USER {db_username} WITH LOGIN PASSWORD '{db_password}';
CREATE DATABASE {db_database};
\\c {db_database};
GRANT ALL PRIVILEGES ON DATABASE {db_database} to {db_username};
-- Used for top-right Technique search - WORD_SIMILARITY()
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;
-- fake mutable unaccent function for full search
CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;
DROP FUNCTION IF EXISTS imm_unaccent;
CREATE FUNCTION imm_unaccent(text) RETURNS text AS $$
BEGIN
    RETURN unaccent($1);
END;
$$ LANGUAGE plpgsql IMMUTABLE;
-- Dictionary for Full Search, doesn't remove stop words "a", "the", ..
DROP TEXT SEARCH CONFIGURATION IF EXISTS english_nostop;
DROP TEXT SEARCH DICTIONARY IF EXISTS english_stem_nostop;
CREATE TEXT SEARCH DICTIONARY english_stem_nostop (template = snowball, language = english);
CREATE TEXT SEARCH CONFIGURATION english_nostop (copy = english);
ALTER TEXT SEARCH CONFIGURATION english_nostop ALTER MAPPING REPLACE english_stem WITH english_stem_nostop;
"""

introduction_text = """
This script reads your .env file as input!

This script creates
-------------------
- init.sql  (in decider root)
  > creates DB 'decider' (DB_DATABASE), DB user, and sets-up needed functionality.

- user.json (in app/utils/jsons/source)
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


def postgres_md5_pass(username: str, password: str) -> str:
    bytes = f"{password}{username}".encode(encoding="utf-8")
    digest = hashlib.md5(bytes).hexdigest()
    return f"md5{digest}"


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

    # postgres strings escape ' as ''
    print("Creating init.sql...  ", end="")

    with open(init_sql_p, "xt") as sql_file:
        sql_file.write(
            init_sql_template.format(
                db_username=DB_USERNAME,
                db_password=postgres_md5_pass(DB_USERNAME, DB_PASSWORD),
                db_database=DB_DATABASE,
            )
        )

    print("done!")

    # -----------------------------------------------------------------------------------------------------------------
    # write 'user.json'

    user_json_p = decider_rel_to_abs_path("./app/utils/jsons/source/user.json")

    # add entry with hashed password
    print("Creating user.json... ", end="")

    user_json_content = [
        {
            "email": ADMIN_EMAIL,
            "password": bcrypt.hashpw(ADMIN_PASS.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            "role_id": 3,
        }
    ]

    with open(user_json_p, "xt") as user_json:
        json.dump(user_json_content, user_json, indent=4)

    print("done!")
    # -----------------------------------------------------------------------------------------------------------------


if __name__ == "__main__":
    main()
