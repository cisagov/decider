from app.models import db, Aka, technique_aka_map

import app.utils.db.read as db_read

from app.utils.db.util import messaged_timer


@messaged_timer("Removing a version from the Akas table")
def drop_version(version):
    tech_uids = db_read.attack.tech_uids(version)

    delete_aka_refs = technique_aka_map.delete().where(technique_aka_map.c.technique.in_(tech_uids))
    db.session.execute(delete_aka_refs)
    db.session.commit()

    referenced_aka_uids = [r[0] for r in db.session.query(technique_aka_map.c.aka).all()]
    delete_unreferenced_akas = Aka.__table__.delete().where(Aka.uid.notin_(referenced_aka_uids))
    db.session.execute(delete_unreferenced_akas)
    db.session.commit()
