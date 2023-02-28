from app.models import db, AttackVersion, Technique, Tactic, DataComponent


def versions():
    avs = AttackVersion.query.all()
    return [av.version for av in avs]


def tech_id_to_uid(version):
    tech_ids_uids = (
        db.session.query(Technique.tech_id, Technique.uid).filter(Technique.attack_version == version)
    ).all()
    return {tid: uid for tid, uid in tech_ids_uids}


def tech_uids(version):
    uids = (db.session.query(Technique.uid).filter(Technique.attack_version == version)).all()
    return [row[0] for row in uids]


def tact_uids(version):
    uids = (db.session.query(Tactic.uid).filter(Tactic.attack_version == version)).all()
    return [row[0] for row in uids]


def missing_qna(version):
    def space_str_or_none(item):
        return (item is None) or (not item.strip())

    # all rows need an answer -> we need to be able to get to the content
    # all tactics need a question -> they always lead to techniques
    # base techniques may have a question -> to lead to their sub techniques
    # sub techniques never have a question -> nothing smaller than a sub technique

    missing_content = {}

    tact_id_q_a = (
        db.session.query(Tactic.tact_id, Tactic.tact_question, Tactic.tact_answer)
        .filter(Tactic.attack_version == version)
        .order_by(Tactic.tact_id.asc())
    ).all()

    # Tactic missing a question or an answer causes an entry each
    for tact_id, tact_q, tact_a in tact_id_q_a:
        missing = []
        if space_str_or_none(tact_q):
            missing.append("question")
        if space_str_or_none(tact_a):
            missing.append("answer")
        if missing:
            missing_content[f"Tactic {tact_id}"] = missing

    tech_id_q_a = (
        db.session.query(Technique.tech_id, Technique.tech_question, Technique.tech_answer)
        .filter(Technique.attack_version == version)
        .order_by(Technique.tech_id.asc())
    ).all()

    # Allows for fast checking of if a Tech has children
    tech_ids = {tech_id for tech_id, _, _ in tech_id_q_a}

    for tech_id, tech_q, tech_a in tech_id_q_a:
        missing = []

        # All Techs need an answer
        if space_str_or_none(tech_a):
            missing.append("answer")

        # All Base Techs with Sub Technique children need a question
        if ("." not in tech_id) and (f"{tech_id}.001" in tech_ids) and space_str_or_none(tech_q):
            missing.append("question")

        if missing:
            missing_content[f"Technique {tech_id}"] = missing

    if not missing_content:
        print(f"Missing content for {version}: none")
        return

    print(f"Missing content for {version}:")
    print("------------------------------\n")
    for attack_id, parts_missing in missing_content.items():
        print(f" {attack_id}")
        for part in parts_missing:
            print(f"  - {part}")


def datacomp_id_to_uid(version):
    dc_ids_uids = (
        db.session.query(DataComponent.dc_id, DataComponent.uid).filter(DataComponent.attack_version == version)
    ).all()
    return {dc_id: dc_uid for dc_id, dc_uid in dc_ids_uids}
