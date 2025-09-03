import uuid
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey
from sqlalchemy.types import BigInteger, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Word(db.Model):
    __tablename__ = "words"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    word = db.Column(String, nullable=False)
    meaning = db.Column(JSONB, nullable=False)
    type = db.Column(String, nullable=False)
    phonetic = db.Column(String, nullable=False)
    combination = db.Column(JSONB, nullable=True)

class Company(db.Model):
    __tablename__ = "companies"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(String, nullable=False)
    code = db.Column(String, nullable=False, unique=True)
    total_shares = db.Column(BigInteger, nullable=False)
    float_shares = db.Column(BigInteger, nullable=False)
    insider_shares = db.Column(BigInteger, nullable=False)
    gov_shares = db.Column(BigInteger, nullable=False)

    share_prices = db.relationship("SharePrice", back_populates="company", cascade="all, delete-orphan")
    ownerships = db.relationship("Ownership", back_populates="company", cascade="all, delete-orphan")

class Ownership(db.Model):
    __tablename__ = "ownerships"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(UUID, ForeignKey("companies.id"), nullable=False)
    user_id = db.Column(UUID, ForeignKey("users.id"), nullable=False)
    week = db.Column(BigInteger, nullable=False)
    shares_owned = db.Column(BigInteger, nullable=False)

    company = db.relationship("Company", back_populates="ownerships")
    user = db.relationship("User", back_populates="ownerships")

class SharePrice(db.Model):
    __tablename__ = "share_prices"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(UUID, ForeignKey("companies.id"), nullable=False)
    week = db.Column(BigInteger, nullable=False)
    price = db.Column(Numeric, nullable=False)

    company = db.relationship("Company", back_populates="share_prices")

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(String, nullable=False)
    username = db.Column(String, nullable=False, unique=True)
    password_hash = db.Column(String, nullable=False)
    own_company = db.Column(String, nullable=True)
    color = db.Column(String, nullable=False)
    balance = db.Column(Numeric, nullable=False, default=0)

    ownerships = db.relationship("Ownership", back_populates="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)