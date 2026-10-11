import os
import io
import uuid
import redis
from datetime import datetime
from app.config import settings

from app.celery_app import celery_app
from celery.signals import worker_process_init

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from sqlalchemy.future import select
from sqlalchemy import create_engine, update, insert
from sqlalchemy.orm import sessionmaker

from app.models import User, CertificateItem, CertificateBatch


# Sync form of same redis client
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


# Global session maker placeholder (populated per-process by worker init signal)
SyncSessionLocal = None


@worker_process_init.connect
def init_celery_db(**kwargs):
    """
    Called automatically when a Celery prefork worker process starts up.
    Creates a dedicated synchronous connection pool isolated to THIS specific process.
    """
    global SyncSessionLocal
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    sync_engine = create_engine(
        sync_url,
        pool_size=5,
        max_overflow=5
    )
    SyncSessionLocal = sessionmaker(bind=sync_engine)


def generate_certificate_pdf(file_path: str, user_name: str, course_name: str):
    """
    Renders a professionally styled, publication-ready PDF certificate in landscape mode.
    """
    # Landscape Letter dimensions: 792 x 612 points
    width, height = landscape(letter)
    
    c = canvas.Canvas(file_path, pagesize=landscape(letter))
    
    # 1. Outer Deep Navy Border
    c.setStrokeColor(colors.HexColor("#1A365D"))
    c.setLineWidth(4)
    c.rect(30, 30, width - 60, height - 60)

    # 2. Inner Gold Accent Border
    c.setStrokeColor(colors.HexColor("#D69E2E"))
    c.setLineWidth(1)
    c.rect(38, 38, width - 76, height - 76)

    # 3. Header / Title
    c.setFillColor(colors.HexColor("#1A365D"))
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(width / 2.0, height - 115, "CERTIFICATE OF COMPLETION")

    # 4. Subtitle Prompt
    c.setFont("Helvetica", 14)
    c.setFillColor(colors.HexColor("#4A5568"))
    c.drawCentredString(width / 2.0, height - 155, "This is proudly presented to")

    # 5. Recipient Name (Prominent & Centered)
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(colors.HexColor("#2D3748"))
    c.drawCentredString(width / 2.0, height - 220, user_name)

    # Decorative Underline for Name
    c.setStrokeColor(colors.HexColor("#CBD5E0"))
    c.setLineWidth(1.5)
    c.line(width / 2.0 - 180, height - 235, width / 2.0 + 180, height - 235)

    # 6. Description Text
    c.setFont("Helvetica", 13)
    c.setFillColor(colors.HexColor("#4A5568"))
    c.drawCentredString(width / 2.0, height - 280, "for successfully completing the professional training course")

    # 7. Course Name (Highlighted in Primary Blue)
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(colors.HexColor("#2B6CB0"))
    c.drawCentredString(width / 2.0, height - 325, course_name)

    # 8. Footer Section (Date & Signatures)
    current_date = datetime.utcnow().strftime("%B %d, %Y")
    
    # Date Line (Left side)
    c.setFont("Helvetica", 11)
    c.setFillColor(colors.HexColor("#718096"))
    c.drawString(100, 100, f"Date Issued: {current_date}")
    c.setLineWidth(1)
    c.setStrokeColor(colors.HexColor("#A0AEC0"))
    c.line(90, 120, 260, 120)

    # Signature Line (Right side)
    c.drawRightString(width - 90, 100, "Authorized Signature")
    c.line(width - 260, 120, width - 90, 120)

    c.showPage()
    c.save()


@celery_app.task(name="generate_certificate_chunk_task")
def generate_certificate_chunk_task(batch_id: str, chunk: list, course_name: str):
    redis_key = f"batch:{batch_id}"
    success_count = 0
    failed_count = 0
    
    if SyncSessionLocal is None:
        raise RuntimeError("SyncSessionLocal is not initialized for this worker process.")

    #media/certificates/{batch_id}/
    batch_dir = os.path.join("media", "certificates", batch_id)
    os.makedirs(batch_dir, exist_ok=True)

    #Process chunk and save item records using a synchronous database session
    with SyncSessionLocal() as session:
        for row in chunk:
            user_id = row.get("user_id")
            
            # Validate User (Synchronous query)
            user = session.query(User).filter(User.id == user_id).first()
            
            if not user:
                failed_count += 1
                session.add(CertificateItem(
                    batch_id=batch_id, 
                    user_id=user_id, 
                    status="FAILED", 
                    error_reason="USER_NOT_FOUND"
                ))
                continue
            
            # Generate a 100% unique filename using user_id + short random hash
            unique_filename = f"{user_id}_{uuid.uuid4().hex[:8]}.pdf"
            file_path = os.path.join(batch_dir, unique_filename)
            
            try:
                
                # Render PDF directly to the unique file path via ReportLab
                generate_certificate_pdf(file_path, user.full_name, course_name)
                
                # Save / Log Success with file path reference
                success_count += 1
                session.add(CertificateItem(
                    batch_id=batch_id, 
                    user_id=user_id, 
                    status="SUCCESS",
                    certificate_url=file_path
                ))
            except Exception as pdf_err:
                print(f"Failed to render PDF for user {user_id}: {pdf_err}")
                failed_count += 1
                session.add(CertificateItem(
                    batch_id=batch_id, 
                    user_id=user_id, 
                    status="FAILED",
                    error_reason=f"PDF_RENDER_ERROR: {str(pdf_err)}"
                ))

        # Commit chunk results to PostgreSQL in one batch transaction
        session.commit()

    # Synchronous Atomic Updates to Redis counters for this chunk
    redis_client.hincrby(redis_key, "success", success_count)
    redis_client.hincrby(redis_key, "failed", failed_count)
    processed = redis_client.hincrby(redis_key, "processed", len(chunk))
    total = int(redis_client.hget(redis_key, "total") or 0)
    
    # Check if the entire batch is fully processed
    if processed >= total:
        redis_client.hset(redis_key, "status", "COMPLETED")
        
        # Fetch final aggregate counts from Redis to ensure absolute accuracy
        final_success = int(redis_client.hget(redis_key, "success") or 0)
        final_failed = int(redis_client.hget(redis_key, "failed") or 0)
        
        # Update master batch record in PostgreSQL synchronously
        with SyncSessionLocal() as db_session:
            db_session.execute(
                update(CertificateBatch)
                .where(CertificateBatch.id == batch_id)
                .values(
                    processed_count=processed,
                    success_count=final_success,
                    failed_count=final_failed,
                    status="COMPLETED",
                    completed_at=datetime.utcnow()
                )
            )
            db_session.commit()