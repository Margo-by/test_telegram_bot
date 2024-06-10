from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class UserValue(Base):
    __tablename__ = 'user_values'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    value = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
