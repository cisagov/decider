from app.models import db

from sqlalchemy import func


def max_primary_key(column):
    # returns the highest value in the provided column, gives 0 if non-present
    # mean to be used as max_primary_key(col) + 1 for bulk inserting the next set of rows
    highest = db.session.query(func.max(column)).first()[0]
    if highest is None:
        return 0
    else:
        return highest
