# Use an official, stable, pre-configured Python runtime
FROM python:3.11-slim

# Set system configuration directory rules
WORKDIR /app

# Copy package blueprints into the isolated container
COPY requirements.txt .

# Install dependencies cleanly without system permission locks
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the core bot engine files
COPY . .

# Expose the internal network traffic port
EXPOSE 10000

# Fire up the engine immediately upon launching
CMD ["python", "bot.py"]
