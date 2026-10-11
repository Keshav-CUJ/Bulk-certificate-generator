# Bulk Certificate Generator

This is a certificate generator, but you can generate certificates in bulk, you dont have to send query for each certificate, just put the details in the csv and hit the endpoint it will give you all the certificates.

This implementation is inclined towards scale hence this supports upto 40K certificates (Approx less then 15sec, but depends upon assigned CPU cores), however it was tested for 400K certificates too.

User can test the endpoint with 3 different sizes of input:

1. input_data_4k.csv
2. input_data_40k.csv
3. input_data_400k.csv

All these 3 CSVs will be generated after docker compose and then the endpoint can be tested.
There is a User table in database which gets populated while setup (with username like a1,a2,a3.....), and also corresponding input CSVs get created too.
CSV contains 80% valid and 20% invalid users, so when the certificates are generated you can see it in status endpoint.  

---

## Architecture & Design Patterns

* Input CSV is received as a network stream, so if a stream contains 40K rows so all 40K rows will not be in the memory. We use chunking method in which 1000 rows are processed at once and sent to the Redis Queue for workers to pick them up.
* Fastapi does a validation check for correct CSV headers and then chuck the data in async manner.
* Redis does not only work as a task queue but it also used as a tracking engine for `total`, `processed`, `success`, `failed` counts so that we dont have to write in the database after each chunk.
* For this implementation celery workers are setup with concurrency=2 which means 2 CPU cores can do pdf generation task parallely, workers just read the tasks from queue and then generate the pdfs and after a chunk is porcessed, redis counters are incremented and also bulk write up happens in the database which stores generated certificate's info.
* Bulk write up (For handling write heavy operation), chuck wise processing and Redis counters are the decisions made for scaling up this implementaion.
* While chuck processing each user is validated aginst the actual information in User table, so if the user is present in the database then only the certificate will be generated. This operation is read-heavy and will be considered in next implementation.

## Test results

* 4K test user CSV --> takes ~2sec when concurrency is set to 2
* 40K test user CSV --> takes ~15sec when concurrency is set to 2
* 400K test user CSV --> takes ~120sec when concurrency is set to 2


---

## Tech Stack

* **Backend Framework:** FastAPI (Python 3.10+)
* **Task Queue & Broker:** Celery with Redis backend
* **Database:** PostgreSQL with SQLAlchemy ORM
* **PDF Engine:** ReportLab (Landscape format with custom borders and typography)
* **Caching & State:** Redis



## Complete Project Setup Guide

### Step 1: Clone the Repository & Setup Environment Files

1. Clone your repository and navigate into the project directory:
```bash
git clone https://github.com/Keshav-CUJ/Bulk-certificate-generator
cd bulk-certificate

```


2. Rename the .env.example to .env ans set variables accordingly
```env
POSTGRES_USER=postgres    #You can change this
POSTGRES_PASSWORD=passwd  #You can change this
POSTGRES_DB=Certificate   #Please dont change it
DB_HOST=db                #Keep 'db' for docker setup and 'localhost' for locally setting up

```

---

### Step 2: Build and Launch the Docker Stack

Ensure Docker and Docker Compose are installed on your machine, then spin up the entire architecture (PostgreSQL, Redis, FastAPI, and Celery workers) in detached mode:

```bash
docker compose up --build -d

```

* **What happens here:** PostgreSQL starts up, automatically provisions your database using your `.env` variables, Redis initializes, and both FastAPI and Celery build their images and connect to the services.

---

### Step 3: Seed the Database & Generate Test CSV Files

Using the containerized environment, you can generate your test datasets (`4K`, `40K`, or `400K`) directly into PostgreSQL and output the matching CSV files to your host folder.

* **For 4K Dataset (`a-h` prefix, 800 invalid rows):**
```bash
docker compose run --rm web python seed_data.py 4k

```


* **For 40K Dataset (`i-p` prefix, 8,000 invalid rows):**
```bash
docker compose run --rm web python seed_data.py 40k

```


* **For 400K Dataset (`q-x` prefix, 80,000 invalid rows):**
```bash
docker compose run --rm web python seed_data.py 400k

```



Once complete, the respective CSV file (e.g., `input_data_40K.csv`) will appear in your project root directory.

---

### Step 4: Verify the Services Are Running

You can check the health and logs of your containers at any time:

* **Check running containers:**
```bash
docker compose ps

```


* **View live logs:**
```bash
docker compose logs -f

```



---

### Step 5: Test the API Endpoint

You can now submit a batch generation task to FastAPI. Use `curl` or tools like Postman:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/certificates/batch" -F "file=@input_data_40K.csv" -F "course_name=Distributed Systems with Celery"

```

Generated PDF certificates will be saved securely inside the container and mapped to your local `media/certificates/{batch_id}/` directory.


To monitor the progress of your bulk certificate generation batch, you can use the status checking endpoint. This allows you to track metrics like total records, processed count, success count, failed count, and current status (`PROCESSING`, `COMPLETED`, etc.).


### Check Status via `curl`

Send a `GET` request using the `batch_id returned when you initially submitted your CSV file`:

```bash
curl "http://127.0.0.1:8000/api/v1/certificates/status/btc_<your_batch_id_here>"

```

Replace `{batch_id}` with the actual ID from your database or API response (e.g., `btc_12345`).

---

### Example Response

```json
{
  "id": "btc_12345",
  "course_name": "Advanced FastAPI Mastery",
  "total_count": 40000,
  "processed_count": 35000,
  "success_count": 27000,
  "failed_count": 8000,
  "status": "PROCESSING",
  "created_at": "2026-10-11T22:00:00Z",
  "completed_at": null
}

```

You can poll this endpoint periodically in a loop or check it manually to watch your Celery background workers process large datasets (like your 40K or 400K records) in parallel!