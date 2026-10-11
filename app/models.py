from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(String(64), primary_key=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class CertificateBatch(Base):
    __tablename__ = "certificate_batches"
    id = Column(String(64), primary_key=True)
    course_name = Column(String(255), nullable=False)
    total_count = Column(Integer, default=0, nullable=False)
    processed_count = Column(Integer, default=0, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    status = Column(String(32), default="PROCESSING", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class CertificateItem(Base):
    __tablename__ = "certificate_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(64), ForeignKey("certificate_batches.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False)
    certificate_url = Column(Text, nullable=True)
    error_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)