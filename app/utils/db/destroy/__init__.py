from . import akas, attack, coocs, mismaps

from app.models import db
from app.utils.db.util import messaged_timer


@messaged_timer("Removing all tables from DB")
def all_tables():
    db.drop_all()
    db.session.commit()
