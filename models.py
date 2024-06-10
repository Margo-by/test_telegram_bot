from sqlalchemy import Column, Integer, String, Date
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class UserValue(Base):
    __tablename__ = 'user_values'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    value = Column(String(255), nullable=False)
    created_date = Column(Date, nullable=False, default=datetime.utcnow().date())
