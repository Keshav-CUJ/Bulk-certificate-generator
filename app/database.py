import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings





# 1. Async SQLAlchemy Engine for FastAPI API layer
async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)



# 2. Async Redis Client for real-time progress updates (Onlyused in fastapi status update)
redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)



async def get_db():
    async with AsyncSessionLocal() as session:
        yield session