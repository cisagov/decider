from app.models import (
    User,
    db,
    tactic_ds_map,
    technique_ds_map,
    technique_dc_map,
    DataComponent,
    DataSource,
    Cart,
    Blurb,
    tactic_technique_map,
    technique_platform_map,
    tactic_platform_map,
    Tactic,
    Technique,
    AttackVersion,
    Platform,
    attack_version_platform_map,
)

import app.utils.db.read as db_read
import app.utils.db.destroy as db_destroy

from app.utils.db.util import messaged_timer


@messaged_timer("Removing Carts for version")
def cart_table(version):

    # Cart
    delete_carts = Cart.__table__.delete().where(Cart.attack_version == version)
    db.session.execute(delete_carts)
    db.session.commit()


@messaged_timer("Removing DataSources & DataComponents for version")
def data_comp_src_table(version):
    tech_uids = db_read.attack.tech_uids(version)
    tact_uids = db_read.attack.tact_uids(version)

    # tactic_ds_map
    delete_tact_ds_map = tactic_ds_map.delete().where(tactic_ds_map.c.tactic.in_(tact_uids))
    db.session.execute(delete_tact_ds_map)
    db.session.commit()

    # technique_ds_map
    delete_tech_ds_map = technique_ds_map.delete().where(technique_ds_map.c.technique.in_(tech_uids))
    db.session.execute(delete_tech_ds_map)
    db.session.commit()

    # technique_dc_map
    delete_tech_dc_map = technique_dc_map.delete().where(technique_dc_map.c.technique.in_(tech_uids))
    db.session.execute(delete_tech_dc_map)
    db.session.commit()

    # DataComponent
    delete_datacomp = DataComponent.__table__.delete().where(DataComponent.attack_version == version)
    db.session.execute(delete_datacomp)
    db.session.commit()

    # DataSource
    delete_datasrc = DataSource.__table__.delete().where(DataSource.attack_version == version)
    db.session.execute(delete_datasrc)
    db.session.commit()


@messaged_timer("Removing Blurbs (Technique Usage Exmaples) for version")
def blurb_table(version):
    tech_uids = db_read.attack.tech_uids(version)

    # Blurb
    delete_blurbs = Blurb.__table__.delete().where(Blurb.technique.in_(tech_uids))
    db.session.execute(delete_blurbs)
    db.session.commit()


@messaged_timer("Removing Tactic <-> Technique mappings for version")
def tact_tech_map(version):
    tact_uids = db_read.attack.tact_uids(version)

    # tactic_technique_map
    delete_tact_tech_map = tactic_technique_map.delete().where(tactic_technique_map.c.tactic.in_(tact_uids))
    db.session.execute(delete_tact_tech_map)
    db.session.commit()


@messaged_timer("Removing Technique <-> Platform mappings for version")
def tech_plat_map(version):
    tech_uids = db_read.attack.tech_uids(version)

    # technique_platform_map
    delete_tech_plat_map = technique_platform_map.delete().where(technique_platform_map.c.technique.in_(tech_uids))
    db.session.execute(delete_tech_plat_map)
    db.session.commit()


@messaged_timer("Removing Tactic <-> Platform mappings for version")
def tact_plat_map(version):
    tact_uids = db_read.attack.tact_uids(version)

    # tactic_platform_map
    delete_tact_plat_map = tactic_platform_map.delete().where(tactic_platform_map.c.tactic.in_(tact_uids))
    db.session.execute(delete_tact_plat_map)
    db.session.commit()


@messaged_timer("Removing Techniques for version")
def technique_table(version):

    # Technique
    delete_technique = Technique.__table__.delete().where(Technique.attack_version == version)
    db.session.execute(delete_technique)
    db.session.commit()


@messaged_timer("Remvoing Tactics for version")
def tactic_table(version):

    # Tactic
    delete_tactic = Tactic.__table__.delete().where(Tactic.attack_version == version)
    db.session.execute(delete_tactic)
    db.session.commit()


@messaged_timer("Removing Platforms for version")
def platform_table(version):
    # attack_version_platform_map
    # platforms can be shared across versions
    # pointers from version -> plat# are deleted from the map
    # then, platforms no longer pointed-to by a version can be deleted
    delete_plat_refs = attack_version_platform_map.delete().where(attack_version_platform_map.c.version == version)
    db.session.execute(delete_plat_refs)
    db.session.commit()

    # Platform
    referenced_plat_uids = [r[0] for r in db.session.query(attack_version_platform_map.c.platform).all()]
    delete_unreferenced_plats = Platform.__table__.delete().where(Platform.uid.notin_(referenced_plat_uids))
    db.session.execute(delete_unreferenced_plats)
    db.session.commit()


@messaged_timer("Removing version from AttackVersion(s) table")
def attack_version_table(version):

    # Remove version from any users that had it as their last-visited preference
    db.session.query(User).filter(User.last_attack_ver == version).update({"last_attack_ver": None})
    db.session.commit()

    # AttackVersion
    delete_version = AttackVersion.__table__.delete().where(AttackVersion.version == version)
    db.session.execute(delete_version)
    db.session.commit()


def drop_version(version):

    # Cart
    db_destroy.attack.cart_table(version)

    # Data Components & Sources for ATT&CK 10+
    base_version_num = int(version.replace("v", "").split(".")[0])  # [8], v[8], v[9], v[9].1, v[9].2
    if base_version_num >= 10:
        db_destroy.attack.data_comp_src_table(version)

    # Blurb
    db_destroy.attack.blurb_table(version)

    # -- Optionals -------------------------------
    if db_read.coocs.exists_for_version(version):
        db_destroy.coocs.drop_version(version)

    if db_read.mismaps.exists_for_version(version):
        db_destroy.mismaps.drop_version(version)

    if db_read.akas.exists_for_version(version):
        db_destroy.akas.drop_version(version)
    # --------------------------------------------

    # tactic_technique_map
    db_destroy.attack.tact_tech_map(version)

    # technique_platform_map
    db_destroy.attack.tech_plat_map(version)

    # tactic_platform_map
    db_destroy.attack.tact_plat_map(version)

    # Technique
    db_destroy.attack.technique_table(version)

    # Tactic
    db_destroy.attack.tactic_table(version)

    # attack_version_platform_map & Platform
    db_destroy.attack.platform_table(version)

    # AttackVersion row
    db_destroy.attack.attack_version_table(version)
