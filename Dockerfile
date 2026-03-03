# Backend API + Worker — Python 3.11 slim
FROM python:3.11-slim

WORKDIR /app

# Install system deps needed by some pip packages (e.g. lightgbm, scipy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer-cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY . .

# Make start.sh executable
RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
