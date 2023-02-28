from app.models import db, Mismapping

import app.utils.db.read as db_read

from app.utils.db.util import messaged_timer

import copy


@messaged_timer("Building Mismappings table")
def add_version(version, src_mgr):
    next_mismap_uid = db_read.util.max_primary_key(Mismapping.uid) + 1

    mismaps = copy.deepcopy(src_mgr.mismaps[version].get_data())

    tech_id_to_uid = db_read.attack.tech_id_to_uid(version)

    # ensure defined original
    mismaps = [m for m in mismaps if m["original"] in tech_id_to_uid]

    for uid_offset, mismap in enumerate(mismaps):
        mismap["uid"] = next_mismap_uid + uid_offset
        mismap["original"] = tech_id_to_uid[mismap["original"]]  # always defined
        mismap["corrected"] = tech_id_to_uid.get(mismap["corrected"])  # may be 'N/A', replace with None

    db.session.bulk_insert_mappings(Mismapping, mismaps, render_nulls=True)
    db.session.commit()
