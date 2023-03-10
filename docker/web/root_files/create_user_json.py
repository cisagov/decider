import bcrypt
import json
import os

from app.env_vars import ADMIN_EMAIL, ADMIN_PASS

def main():

    # get path
    decider_root = os.path.dirname(os.path.realpath(__file__))
    rel_path = "./app/utils/jsons/source/user.json"
    abs_path = os.path.abspath(os.path.join(decider_root, rel_path))

    # create entry
    content = [
        {
            "email": ADMIN_EMAIL,
            "password": bcrypt.hashpw(ADMIN_PASS.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            "role_id": 3,
        }
    ]

    # write
    print("Overwriting / creating user.json file with admin (ADMIN_EMAIL, ADMIN_PASS)")
    with open(abs_path, "wt") as user_json:
        json.dump(content, user_json, indent=4)


if __name__ == "__main__":
    main()
