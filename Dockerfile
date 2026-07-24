# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Create a non-root user to run the application for better security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY software/requirements.txt ./software/
RUN pip install --no-cache-dir -r software/requirements.txt

# Copy the hardware and software directories
# (The backend needs both because hardware_adapter.py imports from hardware/)
COPY hardware/ ./hardware/
COPY software/ ./software/

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Set the working directory to where app.py is located
WORKDIR /app/software

# Expose the port the app runs on
EXPOSE 8080

# Command to run Gunicorn instead of Flask's development server
CMD ["gunicorn", "--workers=2", "--bind=0.0.0.0:8080", "app:app"]
