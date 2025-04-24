# Use AWS Lambda's base image for Python 3.11
FROM public.ecr.aws/lambda/python:3.11

# Copy dependencies and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY ./app ./app
COPY main.py .
COPY .env .

# Lambda will now correctly find this
CMD ["main.handler"]
