FROM python:3.12-slim

# Set the working directory
WORKDIR /app

COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the Prometheus port
EXPOSE 8000

# Command to run the script
CMD ["python", "metrics.py"]
