# Use AWS Lambda's base image for Python 3.11
FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Lambda will now correctly find this
CMD ["main.handler"]
