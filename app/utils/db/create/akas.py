from app.models import db, Aka, technique_aka_map

import app.utils.db.read as db_read

from app.utils.db.util import messaged_timer

import copy


@messaged_timer("Building Akas table")
def add_version(version, src_mgr):
    # Determine at what offset to insert Akas
    next_uid_up = db_read.util.max_primary_key(Aka.uid) + 1

    # Allows for conversion of TechID to UID for the mapping table
    tech_id_to_uid = db_read.attack.tech_id_to_uid(version)

    # Load data - [ {"id": "T1003", "akas": ["dump password hashes", ..]}, ..]
    aka_data = copy.deepcopy(src_mgr.akas[version].get_data())

    # Resolver for current AKAs -> UIDs and one for newly made AKAs
    current_term_to_uid = {term: uid for term, uid in db.session.query(Aka.term, Aka.uid).all()}
    new_term_to_uid = {}

    # Process all entries (of which Tech ID mentioned is in this version of ATT&CK)
    for entry in aka_data:
        if entry["id"] not in tech_id_to_uid:
            continue

        # Get the entry terms and iterate over them, they will be
        # mapped to existing & new UIDs
        terms = entry["akas"]
        terms_as_uids = []
        for term in terms:

            # Term->UID already in database
            if term in current_term_to_uid:
                terms_as_uids.append(current_term_to_uid[term])

            # Term->UID already in memory
            elif term in new_term_to_uid:
                terms_as_uids.append(new_term_to_uid[term])

            # new Term->UID mapping
            else:
                new_term_to_uid[term] = next_uid_up  # record map to be added to mappings
                terms_as_uids.append(next_uid_up)
                next_uid_up += 1

        # transform entry's id into Tech UID and Akas in Aka UIDs
        entry["akas"] = terms_as_uids
        entry["id"] = tech_id_to_uid[entry["id"]]

    # Add newly created Akas to Aka
    new_term_to_uid = [{"uid": uid, "term": term} for term, uid in new_term_to_uid.items()]
    db.session.bulk_insert_mappings(Aka, new_term_to_uid, render_nulls=True)
    db.session.commit()

    # Add both new & old mappings to map
    aka_mappings = [{"technique": entry["id"], "aka": aka_uid} for entry in aka_data for aka_uid in entry["akas"]]
    db.session.execute(technique_aka_map.insert().values(aka_mappings))
    db.session.commit()
