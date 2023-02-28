from string import ascii_lowercase
import functools
import dotenv
import bcrypt
import json
import sys
import os
import re

from app.routes.utils import email_validator, password_validator


init_sql_template = """\
-- Flask Connection / Only User
CREATE USER {db_user_name} WITH LOGIN PASSWORD '{db_user_pass}';
CREATE DATABASE decider;
\\c decider;
GRANT ALL PRIVILEGES ON DATABASE decider to {db_user_name};

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


def prompt_until_condition(prompt, cond_func):
    """Repeats an input (prompt) string until the provided condition function (cond_func) is satisfied"""
    while True:
        value = input(prompt).strip()
        if cond_func(value):
            return value
        else:
            print("    (requirements not met, try again)\n")


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
        print("- DB_USER_NAME and DB_USER_PASS can be changed at any time directly in the .env file.")
        print("- Additional admin accounts can be added in-app at any time.")
        print("\nPlease Ctrl-C out, backup your files, and only run this if you have reason.\n")

        try:
            input("[Enter to confirm deletion]")
        except KeyboardInterrupt:
            print("\nExiting!")
            sys.exit(1)

    # -----------------------------------------------------------------------------------------------------------------
    # remove files if they exist

    for info in file_info.values():
        if info["exists"]:
            os.remove(info["abs_path"])

    # -----------------------------------------------------------------------------------------------------------------
    # prompt for fields

    print(
        f"\n{horiz_sep}\nDB_USER_NAME is the username for the Postgres user that Decider will use to make queries.\n"
        "- Length must be 1-63.\n"
        "- Lower-case letters only, no spaces.\n"
    )
    db_user_name = prompt_until_condition(
        "DB_USER_NAME = ", lambda s: (0 < len(s) < 64) and all((c in ascii_lowercase) for c in s)
    )

    print(
        f"\n{horiz_sep}\n"
        "DB_USER_PASS is the password for the prior-mentioned Postgres user.\n"
        "- Must contain: 2 lowercase, 2 uppercase, 2 numbers, and 2 specials.\n"
        "- ASCII only, and a length in 8-99.\n"
    )
    db_user_pass = prompt_until_condition("DB_USER_PASS = ", functools.partial(password_validator, max_len=99))

    print(
        f"\n{horiz_sep}\n"
        "CART_ENC_KEY is used to encrypt carts saved to the DB.\n"
        "- Basically just a password.\n"
        "- Must contain: 2 lowercase, 2 uppercase, 2 numbers, and 2 specials.\n"
        "- ASCII only, and a length in 8-99.\n"
    )
    cart_enc_key = prompt_until_condition("CART_ENC_KEY = ", functools.partial(password_validator, max_len=99))

    print(
        f"\n{horiz_sep}\n"
        "APP_ADMIN_EMAIL is the email for the Decider admin account that you will use in the web app.\n"
        "- More admins can always be made later - but only this account has access at the start.\n"
        "- Must be valid in format (but doesn't actually have to be real).\n"
    )
    app_admin_email = prompt_until_condition("APP_ADMIN_EMAIL = ", email_validator).lower()

    print(
        f"\n{horiz_sep}\n"
        "APP_ADMIN_PASS is the password for the prior-mentioned Decider admin account.\n"
        "- Must contain: 2 lowercase, 2 uppercase, 2 numbers, and 2 specials.\n"
        "- ASCII only, and a length in 8-48.\n"
    )
    app_admin_pass = prompt_until_condition("APP_ADMIN_PASS = ", password_validator)

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

    # create file, then use dotenv setter (slash escaping fixed issues)
    print("Creating .env...      ", end="")
    dotenv_path = file_info[".env"]["abs_path"]
    open(dotenv_path, "xt").close()
    dotenv.set_key(dotenv_path, "DB_USER_NAME", db_user_name.replace("\\", "\\\\"))
    dotenv.set_key(dotenv_path, "DB_USER_PASS", db_user_pass.replace("\\", "\\\\"))
    dotenv.set_key(dotenv_path, "CART_ENC_KEY", cart_enc_key.replace("\\", "\\\\"))
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
