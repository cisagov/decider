from app.models import db, User


def emails():
    rows = db.session.query(User.email).all()
    return [r[0] for r in rows]
