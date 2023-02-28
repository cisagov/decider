from app.models import db, Cart

import app.utils.db.read as db_read

from app.utils.db.util import messaged_timer

import copy


@messaged_timer("Adding Carts (depending on users and versions installed)")
def add_all(src_mgr):
    # used during a fresh build - doesn't clear or work around existing records

    # dependencies of a cart row
    versions = set(db_read.attack.versions())
    emails = set(db_read.user.emails())

    # filter entries missing needed FKs
    carts = copy.deepcopy(src_mgr.cart.get_data())
    for c in carts:
        c["user"] = c["user"].lower()
    carts = [c for c in carts if (c["attack_version"] in versions) and (c["user"] in emails)]

    # fresh IDs
    for ind, cart in enumerate(carts):
        cart["cart_id"] = ind

    # add Carts
    db.session.bulk_insert_mappings(Cart, carts, render_nulls=True)
    db.session.commit()
