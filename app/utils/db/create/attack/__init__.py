from . import postbuild

from app.models import (
    db,
    Tactic,
    Technique,
    Blurb,
    tactic_technique_map,
    technique_platform_map,
    Platform,
    attack_version_platform_map,
    tactic_platform_map,
    technique_dc_map,
    DataSource,
    DataComponent,
    technique_ds_map,
    tactic_ds_map,
    AttackVersion,
)

from sqlalchemy import and_

import app.utils.db.read as db_read
import app.utils.db.create as db_create

from app.utils.db.util import messaged_timer

from collections import defaultdict


@messaged_timer("Building Tactics table")
def tactic_table(version, src_mgr):

    # get ATT&CK matrix and tactics
    attack: dict = src_mgr.attack[version].get_data()
    matrix = next(i for i in attack.values() if i["type"] == "x-mitre-matrix")
    stix_tactics = [i for i in attack.values() if i["type"] == "x-mitre-tactic"]

    # get question / answer content
    tree_qna = src_mgr.tree[version].get_data()

    # holds generated rows
    tactics = []

    # determine last Tactic unique ID and where we insert our new rows
    next_tact_uid = db_read.util.max_primary_key(Tactic.uid) + 1

    # for tactics in matrix
    for uid_offset, tactic_ref in enumerate(matrix["tactic_refs"]):

        # get tactic object and id
        stix_tactic = next(filter(lambda t: t["id"] == tactic_ref, stix_tactics))
        external_reference = stix_tactic["external_references"][0]
        tact_id = external_reference["external_id"]

        # add entry + question / answer content
        tactics.append(
            {
                # fmt: off
                "uid"           : next_tact_uid + uid_offset,
                "attack_version": version,
                "tact_id"       : tact_id,
                "tact_name"     : stix_tactic["name"],
                "tact_url"      : external_reference["url"],
                "tact_answer"   : tree_qna[tact_id]["answer"],
                "tact_question" : tree_qna[tact_id]["question"],
                "tact_shortname": stix_tactic["x_mitre_shortname"],
                # fmt: on
            }
        )

    # save to DB
    db.session.bulk_insert_mappings(Tactic, tactics, render_nulls=True)
    db.session.commit()


@messaged_timer("Building Techniques table")
def technique_table(version, src_mgr):

    # pull Base / Sub Techniques from ATT&CK
    attack: dict = src_mgr.attack[version].get_data()

    stix_techs = [i for i in attack.values() if i["type"] == "attack-pattern"]
    stix_base_techs = [i for i in stix_techs if not i.get("x_mitre_is_subtechnique", False)]
    stix_sub_techs = [i for i in stix_techs if i.get("x_mitre_is_subtechnique", False)]

    # pull question / answer content
    tree_qna = src_mgr.tree[version].get_data()

    # determine where Techniques will be added in table
    next_tech_uid = db_read.util.max_primary_key(Technique.uid) + 1

    # maps Tech ID to generated row, facilitates Sub Tech referencing parent
    base_techniques = {}

    # build Base Techniques
    for technique in stix_base_techs:
        technique_ref = technique["external_references"][0]
        tech_id = technique_ref["external_id"]

        description = db_create.util.transform_description_citations(technique)

        base_techniques[tech_id] = {
            # fmt: off
            "uid"             : next_tech_uid,
            "attack_version"  : version,
            "parent_uid"      : None,
            "tech_id"         : tech_id,
            "tech_name"       : technique["name"],
            "full_tech_name"  : technique["name"],
            "tech_url"        : technique_ref["url"],
            "tech_description": description,
            "tech_answer"     : tree_qna[tech_id]["answer"] if (tech_id in tree_qna) else None,
            "tech_question"   : tree_qna[tech_id]["question"] if (tech_id in tree_qna) else None,
            # fmt: on
        }
        next_tech_uid += 1

    # build Sub Techniques
    sub_techniques = []
    for technique in stix_sub_techs:
        technique_ref = technique["external_references"][0]
        tech_id = technique_ref["external_id"]

        base_tech_id = tech_id.split(".")[0]
        parent_tech = base_techniques[base_tech_id]

        description = db_create.util.transform_description_citations(technique)

        sub_techniques.append(
            {
                # fmt: off
                "uid"             : next_tech_uid,
                "attack_version"  : version,
                "parent_uid"      : parent_tech["uid"],
                "tech_id"         : tech_id,
                "tech_name"       : technique["name"],
                "full_tech_name"  : f"{parent_tech['tech_name']}: {technique['name']}",
                "tech_url"        : technique_ref["url"],
                "tech_description": description,
                "tech_answer"     : tree_qna[tech_id]["answer"] if (tech_id in tree_qna) else None,
                "tech_question"   : tree_qna[tech_id]["question"] if (tech_id in tree_qna) else None,
                # fmt: on
            }
        )
        next_tech_uid += 1

    # join Base / Sub Techniques and add to DB
    all_techniques = list(base_techniques.values()) + sub_techniques
    db.session.bulk_insert_mappings(Technique, all_techniques, render_nulls=True)
    db.session.commit()


@messaged_timer("Building Blurbs (examples) table")
def blurb_table(version, src_mgr):
    attack: dict = src_mgr.attack[version].get_data()
    tech_id_to_uid = db_read.attack.tech_id_to_uid(version)
    blurbs = []

    # locate end of last blurb content in DB
    next_blurb_uid = db_read.util.max_primary_key(Blurb.uid) + 1

    # attack-pattern--8c32eb4d-805f-4fc5-bf60-c4d476c131b5 -> Twxyz.abc
    stixid_to_techid = {
        item_id: item["external_references"][0]["external_id"]
        for item_id, item in attack.items()
        if item["type"] == "attack-pattern"
    }

    for i in attack.values():

        # must be relationship
        if i["type"] != "relationship":
            continue

        # with description
        if "description" not in i:
            continue

        # with start of citation block so we can reference anything
        if "[" not in i["description"]:
            continue

        # must have external reports referenced so there is visitable content
        if "external_references" not in i:
            continue

        # pattern must be in map to get Tech ID
        if i["target_ref"] not in stixid_to_techid:
            continue

        # Tech ID must be in DB to get UID
        tech_id = stixid_to_techid[i["target_ref"]]
        if tech_id not in tech_id_to_uid:
            continue

        # convert MarkDown citations into HTML citations
        sentence = db_create.util.transform_description_citations(i)

        for j in i["external_references"]:
            url = j.get("url")
            file_name = j.get("source_name")

            if url and file_name:
                blurbs.append(
                    {
                        # fmt: off
                        "uid"      : next_blurb_uid,
                        "technique": tech_id_to_uid[tech_id],
                        "sentence" : sentence,
                        "url"      : url,
                        "file_name": file_name,
                        # fmt: on
                    }
                )
                next_blurb_uid += 1

    db.session.bulk_insert_mappings(Blurb, blurbs, render_nulls=True)
    db.session.commit()


@messaged_timer("Building Tactic <-> Technique map")
def tact_tech_map(version, src_mgr):

    attack: dict = src_mgr.attack[version].get_data()
    techid_to_uid = db_read.attack.tech_id_to_uid(version)

    # query Tactics in database for version
    tactic_qry = (db.session.query(Tactic.uid, Tactic.tact_shortname).filter(Tactic.attack_version == version)).all()
    tactics = [
        {
            "uid": uid,
            "shortname": shortname,
        }
        for uid, shortname in tactic_qry
    ]

    # techid: {phase, phase, ..}
    techid_to_phases = {
        # fmt: off
        tech["external_references"][0]["external_id"]: {  # techid: set(...)
            kcp["phase_name"]
            for kcp in tech["kill_chain_phases"]
            if kcp["kill_chain_name"].lower() == "mitre-attack"
        }
        for tech in attack.values()
        if tech["type"] == "attack-pattern"
        # fmt: on
    }

    # phase: {techid, techid, ..}
    phase_to_techids = defaultdict(set)
    for techid, phases in techid_to_phases.items():
        for phase in phases:
            phase_to_techids[phase].add(techid)

    # associate Tactic & Technique UIDs using 'technique.id in tactic.shortname'
    tact_techs = []
    for tactic in tactics:
        phase = tactic["shortname"]
        for techid in phase_to_techids[phase]:
            tact_techs.append({"tactic": tactic["uid"], "technique": techid_to_uid[techid]})

    # add mappings
    db.session.execute(tactic_technique_map.insert().values(tact_techs))
    db.session.commit()


@messaged_timer("Building Platform table (+ mappings to AttackVersion & Technique)")
def platform_table(version, src_mgr):
    old_plat_name_uid = db.session.query(Platform.readable_name, Platform.uid).all()
    old_plat_name_to_uid = {name: uid for name, uid in old_plat_name_uid}
    next_plat_uid = max(list(old_plat_name_to_uid.values()), default=0) + 1

    new_plat_name_to_uid = {}

    attack_version_platform_uids = set()

    tech_id_to_uid = db_read.attack.tech_id_to_uid(version)

    tech_uid_plat_uid = []

    # get techniques
    attack: dict = src_mgr.attack[version].get_data()
    techniques = [i for i in attack.values() if i["type"] == "attack-pattern"]

    for tech in techniques:
        tech_id = tech["external_references"][0]["external_id"]
        tech_uid = tech_id_to_uid.get(tech_id)
        if tech_uid is None:
            continue

        tech_platforms = tech["x_mitre_platforms"]
        for platform in tech_platforms:

            if platform in old_plat_name_to_uid:
                plat_uid = old_plat_name_to_uid[platform]

            elif platform in new_plat_name_to_uid:
                plat_uid = new_plat_name_to_uid[platform]

            else:
                plat_uid = next_plat_uid
                next_plat_uid += 1
                new_plat_name_to_uid[platform] = plat_uid

            tech_uid_plat_uid.append({"technique": tech_uid, "platform": plat_uid})
            attack_version_platform_uids.add(plat_uid)

    new_platforms = [
        {
            # fmt: off
            "uid"          : uid,
            "readable_name": plat_name,
            "internal_name": plat_name.lower().replace(" ", "_"),
            # fmt: on
        }
        for plat_name, uid in new_plat_name_to_uid.items()
    ]
    new_platforms.sort(key=lambda p: p["uid"])  # ensures order of platform uids for clean DB
    db.session.bulk_insert_mappings(Platform, new_platforms, render_nulls=True)
    db.session.commit()

    version_platform_mappings = [
        {"version": version, "platform": platform_uid} for platform_uid in sorted(list(attack_version_platform_uids))
    ]
    db.session.execute(attack_version_platform_map.insert().values(version_platform_mappings))
    db.session.commit()

    tech_uid_plat_uid.sort(key=lambda m: m["technique"])
    db.session.execute(technique_platform_map.insert().values(tech_uid_plat_uid))
    db.session.commit()


@messaged_timer("Building Tactic <-> Platform map")
def tact_plat_map(version, src_mgr):
    tact_uid_plat_uid = (
        db.session.query(Tactic.uid, Platform.uid)
        .distinct(Tactic.uid, Platform.uid)
        .filter(Tactic.attack_version == version)
        .join(tactic_technique_map, tactic_technique_map.c.tactic == Tactic.uid)
        .join(Technique, tactic_technique_map.c.technique == Technique.uid)
        .join(
            technique_platform_map,
            technique_platform_map.c.technique == Technique.uid,
        )
        .join(Platform, technique_platform_map.c.platform == Platform.uid)
        .order_by(Tactic.uid.asc())
    ).all()

    tact_uid_plat_uid = [{"tactic": tact_uid, "platform": plat_uid} for tact_uid, plat_uid in tact_uid_plat_uid]

    db.session.execute(tactic_platform_map.insert().values(tact_uid_plat_uid))
    db.session.commit()


@messaged_timer("Building Data Source table")
def data_source_table(version, src_mgr):

    attack: dict = src_mgr.attack[version].get_data()

    # record active Data Sources
    # 'active' meaning that a DS has at least 1 DC, and that DC detects at least 1 Tech
    # ... otherwise it makes a useless filter options.
    #     See "Cluster" Data Source in Enterprise 11.0 for example.
    active_dss = set()

    # DataComponent -detects-> Technique relationships
    detects_rels = [
        # fmt: off
        i
        for i in attack.values()
        if i["type"] == "relationship"
        and i["relationship_type"] == "detects"
        and i["source_ref"].startswith("x-mitre-data-component--")
        and i["target_ref"].startswith("attack-pattern--")
        # fmt: on
    ]

    for rel in detects_rels:
        # mark the DC's DS as active
        dc_id = rel["source_ref"]
        dc = attack[dc_id]
        ds_id = dc["x_mitre_data_source_ref"]
        active_dss.add(ds_id)

    # only data sources eventually mapping to a tech
    data_sources = [attack[ds_id] for ds_id in active_dss]

    # determine where they'll be inserted
    next_datasrc_uid = db_read.util.max_primary_key(DataSource.uid) + 1

    # create the data sources
    data_source_rows = []
    for uid_offset, ds in enumerate(data_sources):
        internal_name = ds["name"].replace(" ", "_").lower()
        external_reference = ds["external_references"][0]

        data_source_rows.append(
            {
                # fmt: off
                "uid"           : next_datasrc_uid + uid_offset,
                "attack_version": version,
                "ds_id"         : ds["id"],
                "external_id"   : external_reference["external_id"],
                "url"           : external_reference["url"],
                "internal_name" : internal_name,
                "readable_name" : ds["name"],
                # fmt: on
            }
        )

    # insert them
    db.session.bulk_insert_mappings(DataSource, data_source_rows, render_nulls=True)
    db.session.commit()


@messaged_timer("Building Data Component table")
def data_component_table(version, src_mgr):

    # query data components from ATT&CK
    attack: dict = src_mgr.attack[version].get_data()
    data_components = [i for i in attack.values() if i["type"] == "x-mitre-data-component"]

    # determine where they'll be inserted
    next_datacomp_uid = db_read.util.max_primary_key(DataComponent.uid) + 1

    # create the data components
    data_component_rows = []
    for uid_offset, dc in enumerate(data_components):
        internal_name = dc["name"].replace(" ", "_").lower()

        data_component_rows.append(
            {
                # fmt: off
                "uid"           : next_datacomp_uid + uid_offset,
                "attack_version": version,
                "dc_id"         : dc["id"],
                "parent_ds_id"  : dc["x_mitre_data_source_ref"],
                "internal_name" : internal_name,
                "readable_name" : dc["name"],
                # fmt: on
            }
        )

    # insert them
    db.session.bulk_insert_mappings(DataComponent, data_component_rows, render_nulls=True)
    db.session.commit()


@messaged_timer("Building Data Component <-> Technique map")
def tech_datacomp_map(version, src_mgr):

    # get DataComponent -detects-> Technique rels
    attack: dict = src_mgr.attack[version].get_data()
    detects_rels = [
        # fmt: off
        i
        for i in attack.values()
        if i["type"] == "relationship"
        and i["relationship_type"] == "detects"
        and i["source_ref"].startswith("x-mitre-data-component--")
        and i["target_ref"].startswith("attack-pattern--")
        # fmt: on
    ]

    # create map to resolve Technique STIX IDs to ATT&CK IDs
    stixid_to_techid = {
        stix_id: tech["external_references"][0]["external_id"]
        for stix_id, tech in attack.items()
        if tech["type"] == "attack-pattern"
    }

    # get DB UID resolvers for Technique and DataComponent
    tech_id_to_uid = db_read.attack.tech_id_to_uid(version)
    datacomp_id_to_uid = db_read.attack.datacomp_id_to_uid(version)

    # for all ATT&CK Technique <-> DataComponent mappings
    tech_dc_map_rows = []
    for tech_dc in detects_rels:

        # get UID of Technique in relationship
        tech_ref = tech_dc["target_ref"]
        tech_id = stixid_to_techid.get(tech_ref)
        tech_uid = tech_id_to_uid.get(tech_id)

        # get UID of DataComponent in relationship
        datacomp_id = tech_dc["source_ref"]
        datacomp_uid = datacomp_id_to_uid.get(datacomp_id)

        # if both Tech and DataComp exist in DB for this version, add their mapping
        if tech_uid and datacomp_uid:
            tech_dc_map_rows.append({"technique": tech_uid, "data_component": datacomp_uid})

    # insert them
    db.session.execute(technique_dc_map.insert().values(tech_dc_map_rows))
    db.session.commit()


@messaged_timer("Building Data Source <-> Technique map")
def tech_datasrc_map(version, src_mgr):

    # get all Technique <-> DataSource links for version
    tech_uid_datasrc_uid = (
        db.session.query(Technique.uid, DataSource.uid)
        .distinct(Technique.uid, DataSource.uid)
        .filter(Technique.attack_version == version)
        .join(technique_dc_map, Technique.uid == technique_dc_map.c.technique)
        .join(DataComponent, technique_dc_map.c.data_component == DataComponent.uid)
        # explicitly check DataSource version as (DC.parent_ds_id -> DS.ds_id) relationship exists in multiple versions
        .join(
            DataSource,
            and_(
                DataComponent.parent_ds_id == DataSource.ds_id,
                DataSource.attack_version == version,
            ),
        )
    ).all()

    # insert mappings
    tech_dc_map_rows = [
        {"technique": tech_uid, "data_source": datasrc_uid} for tech_uid, datasrc_uid in tech_uid_datasrc_uid
    ]
    db.session.execute(technique_ds_map.insert().values(tech_dc_map_rows))
    db.session.commit()


@messaged_timer("Building Data Source <-> Tactic map")
def tact_datasrc_map(version, src_mgr):

    # get all unique Tactic <-> DataSource links for ATT&CK version
    tact_uid_datasrc_uid = (
        db.session.query(Tactic.uid, DataSource.uid)
        .distinct(Tactic.uid, DataSource.uid)
        .filter(Tactic.attack_version == version)
        .join(tactic_technique_map, Tactic.uid == tactic_technique_map.c.tactic)
        .join(Technique, tactic_technique_map.c.technique == Technique.uid)
        .join(technique_ds_map, Technique.uid == technique_ds_map.c.technique)
        .join(DataSource, technique_ds_map.c.data_source == DataSource.uid)
    ).all()

    # insert rows to map table
    tact_ds_map_rows = [
        {"tactic": tact_uid, "data_source": datasrc_uid} for tact_uid, datasrc_uid in tact_uid_datasrc_uid
    ]
    db.session.execute(tactic_ds_map.insert().values(tact_ds_map_rows))
    db.session.commit()


def add_version(version, src_mgr):

    # attack_version [easy]
    db.session.add(AttackVersion(version=version))
    db.session.commit()

    # technique [subs need parent_uids and base names for their full_name]
    # subtechnique
    db_create.attack.technique_table(version, src_mgr)

    # blurb [based on techniques]
    db_create.attack.blurb_table(version, src_mgr)

    # tactic [platforms get propagated up from techniques]
    db_create.attack.tactic_table(version, src_mgr)

    # tactic_technique_map [both established, add mappings]
    db_create.attack.tact_tech_map(version, src_mgr)

    # platform [assessing presence of all platforms]
    # attack_version_platform_map
    # technique_platform_map
    db_create.attack.platform_table(version, src_mgr)

    # tactic_platform_map [easy]
    db_create.attack.tact_plat_map(version, src_mgr)

    # Data Components & Sources for ATT&CK 10+
    base_version_num = int(version.replace("v", "").split(".")[0])  # [8], v[8], v[9], v[9].1, v[9].2
    if base_version_num >= 10:
        db_create.attack.data_source_table(version, src_mgr)
        db_create.attack.data_component_table(version, src_mgr)
        db_create.attack.tech_datacomp_map(version, src_mgr)
        db_create.attack.tech_datasrc_map(version, src_mgr)
        db_create.attack.tact_datasrc_map(version, src_mgr)

    # Ensures generated TS vector and index exists for Technique table
    db_create.attack.postbuild.add_technique_search_index()

    # Ensures Answer Cards / their subs are searchable
    db_create.attack.postbuild.add_technique_answer_search_facilities()
