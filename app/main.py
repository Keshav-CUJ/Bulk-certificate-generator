import csv
import io
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, redis_client
from app.models import CertificateBatch
from app.tasks import generate_certificate_chunk_task

app = FastAPI(title="Bulk Certificate Generator API")


# Helper to split list into chunks of N size
def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]



@app.post("/api/v1/certificates/batch", status_code=status.HTTP_202_ACCEPTED)
async def submit_certificate_batch(
    file: UploadFile = File(...),
    course_name: str = Form("FastAPI Mastery"),
    db: AsyncSession = Depends(get_db)
):
    # File type validation
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    batch_id = f"btc_{uuid.uuid4().hex[:8]}"

    #Read and Decode Stream Content Safely
    try:
        contents = await file.read()
        decoded_file = contents.decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read or decode CSV file: {str(e)}")
    
    stream = io.StringIO(decoded_file)
    reader = csv.DictReader(stream)

    #Validate CSV Headers
    required_headers = {"user_id", "course_name"}
    if not reader.fieldnames or not required_headers.issubset(set(reader.fieldnames)):
        raise HTTPException(
            status_code=400, 
            detail=f"CSV missing required headers. Required: {list(required_headers)}"
        )

    #Extract Rows ONCE (Avoids iterator exhaustion)
    rows = list(reader)
    total_records = len(rows)

    if total_records == 0:
        raise HTTPException(status_code=400, detail="CSV file contains no data rows.")

    #Save Master Record in PostgreSQL (Async ORM)
    new_batch = CertificateBatch(
        id=batch_id,
        course_name=course_name,
        total_count=total_records,
        status="PROCESSING"
    )
    db.add(new_batch)
    await db.commit()

    #Initialize Redis Real-time Tracking State
    redis_key = f"batch:{batch_id}"
    await redis_client.hset(redis_key, mapping={
        "total": total_records,
        "processed": 0,
        "success": 0,
        "failed": 0,
        "status": "PROCESSING"
    })
    await redis_client.expire(redis_key, 86400)  # 24-hour TTL

    #Dispatch Tasks in Chunks (Size: 1000 rows per job)
    CHUNK_SIZE = 1000
    for chunk in chunk_list(rows, CHUNK_SIZE):
        generate_certificate_chunk_task.delay(batch_id, chunk, course_name)

    #Instant API Response
    return {
        "status": "ACCEPTED",
        "message": "Batch uploaded and queued for background processing.",
        "data": {
            "batch_id": batch_id,
            "total_records": total_records,
            "status_url": f"/api/v1/certificates/status/{batch_id}"
        }
    }


@app.get("/api/v1/certificates/status/{batch_id}")
async def get_batch_status(batch_id: str):
    redis_key = f"batch:{batch_id}"
    data = await redis_client.hgetall(redis_key)
    
    if not data:
        raise HTTPException(status_code=404, detail="Batch ID not found or expired.")

    total = int(data.get("total", 0))
    processed = int(data.get("processed", 0))
    progress_pct = round((processed / total) * 100, 2) if total > 0 else 0.0

    return {
        "batch_id": batch_id,
        "status": data.get("status"),
        "progress": {
            "total": total,
            "processed": processed,
            "success": int(data.get("success", 0)),
            "failed": int(data.get("failed", 0)),
            "percentage": f"{progress_pct}%"
        }
    }