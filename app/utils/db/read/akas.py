from app.models import db, Technique, Aka, technique_aka_map


def exists_for_version(version):
    exists = (
        db.session.query(Technique.attack_version)
        .filter(Technique.attack_version == version)
        .join(technique_aka_map, Technique.uid == technique_aka_map.c.technique)
        .join(Aka, technique_aka_map.c.aka == Aka.uid)
    ).first()
    return (exists is not None) and (len(exists) == 1) and (exists[0] == version)
