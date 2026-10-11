# Use official lightweight Python 3.10 image
FROM python:3.10-slim

# Set working directory inside the container
WORKDIR /app

# Prevent Python from writing pyc files to disc and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies required for building Python packages or ReportLab if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project source code into the container
COPY . /app

# Ensure media directory exists for certificate storage
RUN mkdir -p /app/media/certificates

# Expose the port FastAPI runs on
EXPOSE 8000

# Default command (can be overridden in docker-compose.yml for celery)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]