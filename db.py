import csv
import random
from datetime import datetime, timedelta
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, ForeignKey, Index, create_engine
)
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------------------------------------------------------
# 1. Database Connection String
# Update 'postgres', 'password', 'localhost', '5432', and 'cert_db' to match your PGAdmin setup
# ---------------------------------------------------------
DATABASE_URL = "postgresql://postgres:passwd@localhost:5432/Certificate"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ---------------------------------------------------------
# 2. SQLAlchemy ORM Models
# ---------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)       # e.g. 'usr_a1'
    full_name = Column(String(255), nullable=False) # e.g. 'a1'
    email = Column(String(255), nullable=False)     # e.g. 'a1@test.com'
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_users_id", "id"),
    )


class CertificateBatch(Base):
    __tablename__ = "certificate_batches"

    id = Column(String(64), primary_key=True)                   # e.g., 'btc_12345'
    course_name = Column(String(255), nullable=False)            # e.g., 'Python Mastery'
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
    status = Column(String(32), nullable=False)                # 'SUCCESS', 'FAILED'
    certificate_url = Column(Text, nullable=True)
    error_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_cert_items_batch", "batch_id"),
    )


# ---------------------------------------------------------
# 3. Helper Functions to Generate Dummy Data
# ---------------------------------------------------------
def generate_pattern_names(count_per_prefix=20):
    """Generates names like a1..a20, b1..b20, c1..c20..."""
    prefixes = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
    user_records = []
    
    start_date = datetime(2025, 1, 1)
    
    for prefix in prefixes:
        for i in range(1, count_per_prefix + 1):
            name = f"{prefix}{i}"
            user_id = f"usr_{name}"
            email = f"{name}@test.com"
            # Random date within the last 300 days
            random_days = random.randint(0, 300)
            created_at = start_date + timedelta(days=random_days)
            
            user_records.append({
                "id": user_id,
                "full_name": name,
                "email": email,
                "created_at": created_at
            })
            
    return user_records


def seed_database_and_generate_csv():
    # Step A: Drop and Create Tables
    print(" Creating database tables via ORM...")
    Base.metadata.create_all(bind=engine)
    
    # Step B: Populate Users
    print(" Generating user records...")
    users_data = generate_pattern_names(count_per_prefix=500)  # 8 * 500 = 4000 users
    
    session = SessionLocal()
    try:
        # Clear existing users if re-running
        session.query(User).delete()
        
        db_users = [User(**u) for u in users_data]
        session.bulk_save_objects(db_users)
        session.commit()
        print(f" Successfully inserted {len(db_users)} users into PostgreSQL!")
    except Exception as e:
        session.rollback()
        print(f" Error seeding database: {e}")
        return
    finally:
        session.close()

    # Step C: Generate CSV file with VALID and INVALID User IDs
    print(" Generating 'input_data.csv' with valid & invalid entries...")
    
    # Take 80% valid user IDs from DB
    valid_ids = [u["id"] for u in users_data[:3500]]
    
    # Create 30 fake/invalid user IDs (e.g. usr_invalid_1, usr_z99)
    invalid_ids = [f"usr_invalid_{i}" for i in range(1, 500)]
    
    # Mix them together and shuffle
    all_csv_user_ids = valid_ids + invalid_ids
    random.shuffle(all_csv_user_ids)
    
    csv_filename = "input_data.csv"
    with open(csv_filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["user_id", "course_name"])  # Header
        
        courses = ["FastAPI Mastery", "Async Python Deep Dive", "System Architecture 101"]
        for uid in all_csv_user_ids:
            writer.writerow([uid, random.choice(courses)])
            
    print(f" 'input_data.csv' created with {len(all_csv_user_ids)} rows ({len(valid_ids)} valid, {len(invalid_ids)} invalid)!")


if __name__ == "__main__":
    seed_database_and_generate_csv()