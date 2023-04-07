from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.orm import relationship

from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy_utils import EncryptedType
from sqlalchemy_utils.types.encrypted.encrypted_type import AesEngine, AesGcmEngine

from app.env_vars import CART_ENC_KEY

db = SQLAlchemy()


attack_version_platform_map = db.Table(
    "attack_version_platform_map",
    db.Column("version", db.Text, db.ForeignKey("attack_version.version"), primary_key=True),
    db.Column("platform", db.Integer, db.ForeignKey("platform.uid"), primary_key=True),
)

tactic_platform_map = db.Table(
    "tactic_platform_map",
    db.Column("tactic", db.Integer, db.ForeignKey("tactic.uid"), primary_key=True),
    db.Column("platform", db.Integer, db.ForeignKey("platform.uid"), primary_key=True),
)

technique_platform_map = db.Table(
    "technique_platform_map",
    db.Column("technique", db.Integer, db.ForeignKey("technique.uid"), primary_key=True),
    db.Column("platform", db.Integer, db.ForeignKey("platform.uid"), primary_key=True),
)

tactic_technique_map = db.Table(
    "tactic_technique_map",
    db.Column("tactic", db.Integer, db.ForeignKey("tactic.uid"), primary_key=True),
    db.Column("technique", db.Integer, db.ForeignKey("technique.uid"), primary_key=True),
)

technique_aka_map = db.Table(
    "technique_aka_map",
    db.Column("technique", db.Integer, db.ForeignKey("technique.uid"), primary_key=True),
    db.Column("aka", db.Integer, db.ForeignKey("aka.uid"), primary_key=True),
)

tactic_ds_map = db.Table(
    "tactic_ds_map",
    db.Column("tactic", db.Integer, db.ForeignKey("tactic.uid"), primary_key=True),
    db.Column("data_source", db.Integer, db.ForeignKey("data_source.uid"), primary_key=True),
)

technique_ds_map = db.Table(
    "technique_ds_map",
    db.Column("technique", db.Integer, db.ForeignKey("technique.uid"), primary_key=True),
    db.Column("data_source", db.Integer, db.ForeignKey("data_source.uid"), primary_key=True),
)

technique_dc_map = db.Table(
    "technique_dc_map",
    db.Column("technique", db.Integer, db.ForeignKey("technique.uid"), primary_key=True),
    db.Column(
        "data_component",
        db.Integer,
        db.ForeignKey("data_component.uid"),
        primary_key=True,
    ),
)


class AttackVersion(db.Model):
    version = db.Column(db.Text, primary_key=True)
    platforms = relationship(
        "Platform",
        secondary=attack_version_platform_map,
        lazy="select",
        order_by="Platform.uid",
    )
    tactics = relationship("Tactic", lazy="select", order_by="Tactic.uid")
    techniques = relationship("Technique", lazy="select", order_by="Technique.tech_id")
    data_sources = relationship("DataSource", lazy="select", order_by="DataSource.uid")
    data_components = relationship("DataComponent", lazy="select", order_by="DataComponent.uid")


class Platform(db.Model):
    uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    internal_name = db.Column(db.Text, nullable=False)  # ex: office_365 (space-free unique identifier for backend)
    readable_name = db.Column(db.Text, nullable=False)  # ex: Office 365


class Tactic(db.Model):
    uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    attack_version = db.Column(db.Text, db.ForeignKey("attack_version.version"), nullable=False)
    tact_id = db.Column(db.Text, nullable=False)
    tact_name = db.Column(db.Text, nullable=False)
    tact_url = db.Column(db.Text, nullable=False)
    tact_answer = db.Column(db.Text, nullable=False)
    tact_question = db.Column(db.Text, nullable=False)
    tact_shortname = db.Column(db.Text, nullable=False)


class Technique(db.Model):
    uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    attack_version = db.Column(db.Text, db.ForeignKey("attack_version.version"), nullable=False)
    parent_uid = db.Column(db.Integer, db.ForeignKey("technique.uid"))  # define if sub-tech, null if base-tech
    tech_id = db.Column(db.Text, nullable=False)
    tech_name = db.Column(db.Text, nullable=False)

    # Case Twxyz     : "Base Technique Name"
    # Case Twxyz.abc : "Base Technique Name: Sub Technique Name"
    full_tech_name = db.Column(db.Text, nullable=False)

    tech_url = db.Column(db.Text, nullable=False)
    tech_description = db.Column(db.Text, nullable=False)
    tech_answer = db.Column(db.Text)
    tech_question = db.Column(db.Text)  # null if sub-tech or if base-tech without sub-techs

    # created in postbuild.py
    tech_ts = db.Column(TSVECTOR)  # based on tech_id, tech_description, full_tech_name
    tech_ans_ts = db.Column(TSVECTOR)  # based on tech_answer


class Aka(db.Model):
    uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    term = db.Column(db.Text, nullable=False)


class Blurb(db.Model):
    uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    technique = db.Column(db.Integer, db.ForeignKey("technique.uid"), nullable=False)
    file_name = db.Column(db.Text, nullable=False)
    url = db.Column(db.Text, nullable=False)
    sentence = db.Column(db.Text, nullable=False)


class Mismapping(db.Model):
    uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    original = db.Column(db.Integer, db.ForeignKey("technique.uid"), nullable=False)
    corrected = db.Column(db.Integer, db.ForeignKey("technique.uid"))
    context = db.Column(db.Text)
    rationale = db.Column(db.Text)


class CoOccurrence(db.Model):
    technique_i = db.Column(db.Integer, db.ForeignKey("technique.uid"), primary_key=True, nullable=False)
    technique_j = db.Column(db.Integer, db.ForeignKey("technique.uid"), primary_key=True, nullable=False)
    score = db.Column(db.Float, nullable=False)
    i_references = db.Column(db.Integer, nullable=False)
    j_references = db.Column(db.Integer, nullable=False)
    shared_references = db.Column(db.Integer, nullable=False)
    shared_percent = db.Column(db.Integer, nullable=False)
    j_avg = db.Column(db.Float, nullable=False)
    j_std = db.Column(db.Float, nullable=False)


class Role(db.Model):
    role_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text)
    description = db.Column(db.Text)
    users = db.relationship("User", back_populates="role")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(320), unique=True)

    # Uses bcrypt.hashpw(password, bcrypt.gensalt()), it is not plaintext
    password = db.Column(db.Text)

    session_token = db.Column(db.String(40), index=True, unique=True)
    role_id = db.Column(db.Integer, db.ForeignKey("role.role_id"), nullable=False)
    role = db.relationship("Role", back_populates="users")
    last_attack_ver = db.Column(db.Text, db.ForeignKey("attack_version.version"))

    def get_id(self):
        """required as it overrides a UserMixin function so that session_tokens can be used as alternative tokens"""
        return self.session_token


class Cart(db.Model):
    """Represents a CTI Report (editable in the 'shopping-cart'-style interface, hence the name)
    cart_name    : uses the weaker AesEngine encryption (same IV) to allow checking for name collisions (per user)
    cart_content : uses the strong AesGcmEngine enc (randomized IV) to store mapped entries / rationale
    """

    cart_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user = db.Column(db.Text, db.ForeignKey("user.email"), nullable=False)
    attack_version = db.Column(db.Text, db.ForeignKey("attack_version.version"), nullable=False)
    last_modified = db.Column(db.DateTime, nullable=False)
    cart_name = db.Column(EncryptedType(db.Text, CART_ENC_KEY, AesEngine, "pkcs5"), nullable=False)
    cart_content = db.Column(EncryptedType(db.Text, CART_ENC_KEY, AesGcmEngine), nullable=False)


class DataSource(db.Model):
    uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    attack_version = db.Column(db.Text, db.ForeignKey("attack_version.version"), nullable=False)
    ds_id = db.Column(db.Text, nullable=False)
    external_id = db.Column(db.Text, nullable=False)
    url = db.Column(db.Text, nullable=False)
    internal_name = db.Column(db.Text, nullable=False)
    readable_name = db.Column(db.Text, nullable=False)


class DataComponent(db.Model):
    uid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    attack_version = db.Column(db.Text, db.ForeignKey("attack_version.version"), nullable=False)
    dc_id = db.Column(db.Text, nullable=False)
    parent_ds_id = db.Column(db.Text, nullable=False)
    internal_name = db.Column(db.Text, nullable=False)
    readable_name = db.Column(db.Text, nullable=False)
