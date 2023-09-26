import bcrypt
import json
import os

from app.env_vars import APP_ADMIN_EMAIL, APP_ADMIN_PASS


def main():
    # get path
    decider_root = os.path.dirname(os.path.realpath(__file__))
    rel_path = "config/build_sources/user.json"
    abs_path = os.path.abspath(os.path.join(decider_root, rel_path))

    # create entry
    content = [
        {
            "email": APP_ADMIN_EMAIL,
            "password": bcrypt.hashpw(APP_ADMIN_PASS.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            "role_id": 3,
        }
    ]

    # write
    print("Creating user.json file with admin (APP_ADMIN_EMAIL, APP_ADMIN_PASS)")
    with open(abs_path, "wt") as user_json:
        json.dump(content, user_json, indent=4)


if __name__ == "__main__":
    main()
