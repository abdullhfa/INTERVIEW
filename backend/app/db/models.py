from sqlalchemy import Column, String, JSON
from app.db.database import Base

class ProfileModel(Base):
    __tablename__ = "profiles"
    id = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)

class SessionModel(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True)
    data = Column(JSON, nullable=False)
