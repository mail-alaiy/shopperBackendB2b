FROM python:3.11

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY ./requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the main application entrypoint and the app directory
COPY ./main.py ./
COPY ./app ./app

# .env file is handled by docker-compose environment/env_file, no need to copy here
# COPY ./.env .

# Expose the port the app runs on
EXPOSE 8005

# Command to run the application using the main app object
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8005"] 