FROM python:3.9-slim

WORKDIR /app

# Copy requirements from backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire repository
COPY . .

# Set working directory to backend so uvicorn finds main.py
WORKDIR /app/backend

# Hugging Face Spaces expects the app on port 7860
EXPOSE 7860

# Start the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
