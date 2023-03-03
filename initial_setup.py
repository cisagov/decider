from string import ascii_lowercase
import functools
import dotenv
import bcrypt
import json
import sys
import os
import re

from app.routes.utils import email_validator, password_validator
from app.env_vars import DB_USERNAME, DB_PASSWORD, DB_HOSTNAME, DB_PORT, DB_DATABASE, CART_ENC_KEY, ADMIN_EMAIL, ADMIN_PASS


init_sql_template = """\
-- Flask Connection / Only User

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

horiz_sep = "-" * 80
introduction_text = """
This script creates:
- init.sql  (in decider root)
- .env      (in decider root)
- user.json (in app/utils/jsons/source)

init.sql : Creates DB 'decider', DB user, and sets-up needed functionality.

.env : Holds DB user name/pass and a cart encryption key used by Decider.

user.json : An entry for a Decider Admin is created, so it is usable after build.

You will be creating 2 logins and an encryption key.
"""


email_format_regex = re.compile(
    r"""(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@"""
    r"""((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))"""
)

file_info = {
    "init.sql": {"rel_path": "./init.sql"},
    ".env": {"rel_path": "./.env"},
    "user.json": {"rel_path": "./app/utils/jsons/source/user.json"},
}


def main():
    # -----------------------------------------------------------------------------------------------------------------
    # welcome, check if script was ran before

    print(introduction_text)

    # get file paths / state
    decider_root = os.path.dirname(os.path.realpath(__file__))
    for info in file_info.values():
        info["abs_path"] = os.path.abspath(os.path.join(decider_root, info["rel_path"]))
        info["exists"] = os.path.exists(info["abs_path"])

    # warn if files already present
    existing_files = [name for name, info in file_info.items() if info["exists"]]
    if len(existing_files) > 0:
        print("WARNING: This script has been run before.")
        print(f"- The following files were already created: {existing_files}.")
        print("- Unless existing carts were cleared, changing CART_ENC_KEY will cause errors and inaccessible carts.")
        print("- DB_USERNAME and DB_PASSWORD can be changed at any time directly in the .env file.")
        print("- Additional admin accounts can be added in-app at any time.")
        print("\nPlease Ctrl-C out, backup your files, and only run this if you have reason.\n")


    db_user_name = DB_USERNAME
    db_user_pass = DB_PASSWORD
    cart_enc_key = CART_ENC_KEY
    app_admin_email = ADMIN_EMAIL
    app_admin_pass = ADMIN_PASS

    # -----------------------------------------------------------------------------------------------------------------
    # create files

    # postgres strings escape ' as ''
    print("\nCreating init.sql...  ", end="")
    with open(file_info["init.sql"]["abs_path"], "xt") as sql_file:
        sql_file.write(
            init_sql_template.format(
                db_user_name=db_user_name.replace("'", "''"), db_user_pass=db_user_pass.replace("'", "''")
            )
        )
    print("done!")

    # add entry with hashed password
    print("Creating user.json... ", end="")
    with open(file_info["user.json"]["abs_path"], "xt") as user_json:
        user_json_data = [
            {
                "email": app_admin_email,
                "password": bcrypt.hashpw(app_admin_pass.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
                "role_id": 3,
            }
        ]
        json.dump(user_json_data, user_json, indent=4)
    print("done!")


if __name__ == "__main__":
    main()
