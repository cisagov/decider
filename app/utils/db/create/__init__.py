from . import akas, attack, cart, coocs, mismaps, role, user, util

from app.models import db
from app.utils.db.util import messaged_timer


@messaged_timer("Adding tables to DB")
def all_tables():
    db.create_all()
    db.session.commit()
