from app.models import db, Role

from app.utils.db.util import messaged_timer


@messaged_timer("Building Role table")
def add_all(src_mgr):
    # used during a fresh build - doesn't clear or work around existing records
    role_data = src_mgr.role.get_data()
    db.session.bulk_insert_mappings(Role, role_data, render_nulls=True)
    db.session.commit()
