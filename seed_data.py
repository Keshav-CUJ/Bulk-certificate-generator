import csv
import random
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Base, User

# Convert async SQLAlchemy URL to sync driver URL for the seeding script
sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

engine = create_engine(sync_url, echo=False)
SessionLocal = sessionmaker(bind=engine)


def generate_pattern_names(prefixes: list, total_users: int):
    """Generates user records dynamically using the provided prefix block."""
    user_records = []
    start_date = datetime(2025, 1, 1)
    
    count_per_prefix = max(1, total_users // len(prefixes))
    
    for prefix in prefixes:
        for i in range(1, count_per_prefix + 1):
            name = f"{prefix}{i}"
            user_id = f"usr_{name}"
            email = f"{name}@test.com"
            random_days = random.randint(0, 300)
            created_at = start_date + timedelta(days=random_days)
            
            user_records.append({
                "id": user_id,
                "full_name": name,
                "email": email,
                "created_at": created_at
            })
            
    return user_records


def seed_database_and_generate_csv(size_type="40k"):
    # Size tier configuration mapping with exact prefix blocks and invalid counts
    config_map = {
        "4k": {
            "prefixes": ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
            "users": 4000, 
            "invalid": 800, 
            "filename": "input_data_4K.csv"
        },
        "40k": {
            "prefixes": ['i', 'j', 'k', 'l', 'm', 'n', 'o', 'p'],
            "users": 40000, 
            "invalid": 8000, 
            "filename": "input_data_40K.csv"
        },
        "400k": {
            "prefixes": ['q', 'r', 's', 't', 'u', 'v', 'w', 'x'],
            "users": 400000, 
            "invalid": 80000, 
            "filename": "input_data_400K.csv"
        },
    }
    
    cfg = config_map.get(size_type, config_map["40k"])
    prefixes = cfg["prefixes"]
    total_users = cfg["users"]
    invalid_count = cfg["invalid"]
    csv_filename = cfg["filename"]

    print(f"Creating database tables via ORM if not present...")
    Base.metadata.create_all(bind=engine)

    print(f"Generating {total_users} user records in memory using prefixes {prefixes}...")
    users_data = generate_pattern_names(prefixes, total_users=total_users)
    
    session = SessionLocal()
    try:
        print("Clearing existing users and inserting new batch...")
        session.query(User).delete()
        session.commit()
        
        # Batch insert to prevent memory spikes on large sizes (like 400k)
        batch_size = 5000
        for i in range(0, len(users_data), batch_size):
            chunk = [User(**u) for u in users_data[i:i + batch_size]]
            session.bulk_save_objects(chunk)
            session.commit()
            
        print(f"Successfully inserted {len(users_data)} users into PostgreSQL!")
    except Exception as e:
        session.rollback()
        print(f"Error seeding database: {e}")
        return
    finally:
        session.close()

    print(f"Generating '{csv_filename}' with valid & invalid entries...")
    valid_ids = [u["id"] for u in users_data[:total_users - invalid_count]]
    invalid_ids = [f"usr_invalid_{i}" for i in range(1, invalid_count + 1)]
    
    all_csv_user_ids = valid_ids + invalid_ids
    random.shuffle(all_csv_user_ids)

    with open(csv_filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["user_id", "course_name"])  # Header
        
        courses = ["FastAPI Mastery", "Async Python Deep Dive", "System Architecture 101"]
        for uid in all_csv_user_ids:
            writer.writerow([uid, random.choice(courses)])
            
    print(f"'{csv_filename}' created with {len(all_csv_user_ids)} rows ({len(valid_ids)} valid, {invalid_count} invalid)!")


if __name__ == "__main__":
    size = sys.argv[1] if len(sys.argv) > 1 else "40k"
    seed_database_and_generate_csv(size)