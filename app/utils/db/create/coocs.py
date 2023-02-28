from app.models import db, CoOccurrence

import app.utils.db.read as db_read

from app.utils.db.util import messaged_timer


@messaged_timer("Building Co-occurrences table")
def add_version(version, src_mgr):
    tech_id_to_uid = db_read.attack.tech_id_to_uid(version)

    # for all Co-occurrences
    co_ocs = src_mgr.co_ocs[version].get_data()
    co_oc_rows = []
    for co_oc in co_ocs:

        # if ID -> UID resolution possible (should always be..
        # but if you mix versions.. nope)
        tech_i_uid = tech_id_to_uid.get(co_oc["technique_i"])
        tech_j_uid = tech_id_to_uid.get(co_oc["technique_j"])
        if tech_i_uid and tech_j_uid:

            # add entry with UIDs in place of IDs
            co_oc_rows.append({**co_oc, "technique_i": tech_i_uid, "technique_j": tech_j_uid})

    # insert rows
    db.session.bulk_insert_mappings(CoOccurrence, co_oc_rows, render_nulls=True)
    db.session.commit()
