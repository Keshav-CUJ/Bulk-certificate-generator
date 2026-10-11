# Bulk Certificate Generator

A production-grade, memory-efficient bulk certificate generation and tracking engine built with **FastAPI**, **Celery**, **PostgreSQL**, **Redis**, and **ReportLab**.

Designed to handle multi-gigabyte CSV uploads and generate thousands of publication-ready PDF certificates in parallel without blocking the main event loop or overloading system memory.

---

## Architecture & Design Patterns

* **Web-Queue-Worker Pattern:** FastAPI acts as a high-speed ingestion and streaming layer, offloading CPU-bound PDF rendering tasks to a distributed **Celery** background worker queue.
* **Streaming CSV Chunker:** Processes massive CSV files row-by-row using low-overhead streams, preventing out-of-memory (OOM) crashes on large datasets.
* **Hybrid Async/Sync DB Strategy:**
* **FastAPI Layer:** Uses asynchronous SQLAlchemy (`asyncpg`) for non-blocking HTTP request handling.
* **Celery Worker Layer:** Uses synchronous SQLAlchemy sessions initialized safely per worker process via Celery signals (`worker_process_init`), bypassing GIL constraints and event loop clashes.


* **Real-Time Tracking:** Redis hashes and atomic counters (`hincrby`) track batch processing progress (`total`, `processed`, `success`, `failed`) in real time.

---

## Tech Stack

* **Backend Framework:** FastAPI (Python 3.10+)
* **Task Queue & Broker:** Celery with Redis backend
* **Database:** PostgreSQL with SQLAlchemy ORM
* **PDF Engine:** ReportLab (Landscape format with custom borders and typography)
* **Caching & State:** Redis

---

## Project Directory Structure

```text
bulk-certificate/
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI entrypoint & streaming batch endpoint
│   ├── celery_app.py      # Celery application configuration
│   ├── database.py        # Async engine & session setup for FastAPI
│   ├── models.py          # SQLAlchemy models (User, CertificateBatch, CertificateItem)
│   ├── tasks.py           # Synchronous Celery worker tasks & ReportLab PDF generator
│   └── config.py          # Application configuration & environment settings
├── media/
│   └── certificates/      # Generated PDF output storage organized by batch ID
├── requirements.txt       # Project Python dependencies
└── README.md

```

---

## Prerequisites

Make sure you have the following services installed and running locally:

* **Python 3.10+**
* **PostgreSQL**
* **Redis Server**

---

## Local Setup Instructions

### 1. Clone and Navigate to the Repository

```bash
git clone <your-repository-url>
cd bulk-certificate

```

### 2. Create and Activate a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate

```

### 3. Install Dependencies

```bash
pip install fastapi uvicorn celery redis sqlalchemy asyncpg psycopg2-binary reportlab pydantic-settings

```

### 4. Configure Environment Variables

Create a `.env` file in the root directory:

```env
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/certificate_db
REDIS_URL=redis://localhost:6379/0

```

---

## Running the Application

To run the system locally, you need three separate terminal windows:

### Terminal 1: Start Redis Server

```bash
redis-server

```

### Terminal 2: Start Celery Worker

Run the Celery worker with the prefork pool enabled and your desired concurrency level (e.g., matching your CPU core count):

```bash
celery -A app.tasks.celery_app worker --pool=prefork --concurrency=2 --loglevel=info

```

### Terminal 3: Start FastAPI Server

Start the Uvicorn development server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

```

---

## API Usage Example

### Submit a Certificate Batch

Send a multi-part form request with a CSV file containing columns `user_id` and `course_name`.

```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/certificates/batch' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'course_name=Advanced FastAPI Mastery' \
  -F 'file=@path/to/your/users.csv'

```

**Successful Response (`202 Accepted`):**

```json
{
  "status": "ACCEPTED",
  "message": "Batch uploaded and queued for background processing.",
  "data": {
    "batch_id": "btc_a1b2c3d4",
    "total_records": 1000,
    "status_url": "/api/v1/certificates/status/btc_a1b2c3d4"
  }
}

```

---

## Next Steps

* Containerizing the application stack (`Dockerfile` + `docker-compose.yml`) for seamless one-command deployment.