from app.models import db, CoOccurrence

from app.utils.db.util import messaged_timer

import app.utils.db.read as db_read

from sqlalchemy import or_


@messaged_timer("Removing a version from the Co-occurrences table")
def drop_version(version):
    tech_uids = db_read.attack.tech_uids(version)
    delete_co_ocs = CoOccurrence.__table__.delete().where(
        or_(
            CoOccurrence.technique_i.in_(tech_uids),
            CoOccurrence.technique_j.in_(tech_uids),
        )
    )
    db.session.execute(delete_co_ocs)
    db.session.commit()
