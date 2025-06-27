FROM python:3.11-slim

# Install ffmpeg for yt-dlp
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Set working directory
WORKDIR /app

# Copy all files into container
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
