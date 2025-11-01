FROM python:3.14-slim

# Set the working directory
WORKDIR /app

COPY LICENSE metrics.py /app/

# Install dependencies
RUN --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    pip install --no-cache-dir --requirement /tmp/requirements.txt

# Expose the Prometheus port
EXPOSE 8000

# Command to run the script
CMD ["python", "metrics.py"]
