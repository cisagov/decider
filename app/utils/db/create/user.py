from app.models import db, User

from app.utils.db.util import messaged_timer

import copy


@messaged_timer("Building User table")
def add_all(src_mgr):
    # used during a fresh build - doesn't clear or work around existing records
    user_data = copy.deepcopy(src_mgr.user.get_data())

    # enumerates entries and clears values that get set in-app
    for ind, entry in enumerate(user_data):
        entry["id"] = ind
        entry["session_token"] = None
        entry["last_attack_ver"] = None

    db.session.bulk_insert_mappings(User, user_data, render_nulls=True)
    db.session.commit()
