from app.models import db, Technique, Mismapping


def exists_for_version(version):
    exists = (
        db.session.query(Technique.attack_version)
        .filter(Technique.attack_version == version)
        .join(Mismapping, Technique.uid == Mismapping.original)
    ).first()
    return (exists is not None) and (len(exists) == 1) and (exists[0] == version)
