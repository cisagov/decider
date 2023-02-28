from app.models import db, Mismapping

from app.utils.db.util import messaged_timer

import app.utils.db.read as db_read

from sqlalchemy import or_


@messaged_timer("Removing a version from the Mismappings table")
def drop_version(version):
    tech_uids = db_read.attack.tech_uids(version)
    delete_co_ocs = Mismapping.__table__.delete().where(
        or_(
            Mismapping.original.in_(tech_uids),
            Mismapping.corrected.in_(tech_uids),
        )
    )
    db.session.execute(delete_co_ocs)
    db.session.commit()
