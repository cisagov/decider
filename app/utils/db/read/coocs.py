from app.models import db, Technique, CoOccurrence


def exists_for_version(version):
    exists = (
        db.session.query(Technique.attack_version)
        .filter(Technique.attack_version == version)
        .join(CoOccurrence, Technique.uid == CoOccurrence.technique_i)
    ).first()
    return (exists is not None) and (len(exists) == 1) and (exists[0] == version)
