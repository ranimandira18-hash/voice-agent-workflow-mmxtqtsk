FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for LiveKit RTC and audio processing
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    libglib2.0-0 \
    libgobject-2.0-0 \
    libgstreamer1.0-0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY agent/ ./agent/

CMD ["python", "agent/main.py", "start"]

