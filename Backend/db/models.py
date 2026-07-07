## postgres

from sqlalchemy import Column , String , Boolean , DateTime
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class VerifiedTarget(Base):
    __tablename__ = "verified_targets"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    target_type = Column(String)  # "domain" or "repo"
    target_value = Column(String)  # domain name or repo url
    verification_token = Column(String, nullable=True)
    verified = Column(Boolean, default=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)