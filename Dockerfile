FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    libgomp1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY NoteMasterAI/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY NoteMasterAI/ /app/NoteMasterAI/

# Set environment variables
ENV PYTHONPATH=/app/NoteMasterAI
ENV PYTHONUNBUFFERED=1

EXPOSE 5000 5005/udp

# Run transfer server
CMD ["python", "NoteMasterAI/logic/transfer_server.py"]
