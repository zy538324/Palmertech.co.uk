# Use an official lightweight Python image.
FROM python:3.12-slim

# Ensure Python output is sent straight to the terminal without buffering.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies first to take advantage of Docker layer caching.
COPY requirements.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libfreetype6-dev libjpeg-dev zlib1g-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the remainder of the application code.
COPY . .

# Create a non-root user to run the app and ensure it owns the working tree.
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app

USER appuser

# Cloud Run injects the PORT environment variable; default to 8080 for local runs.
ENV PORT=8080
EXPOSE 8080

# Start the Flask application via the main module so CLI flags remain available.
CMD ["python", "app.py"]
