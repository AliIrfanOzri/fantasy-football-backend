FROM python:3.12.0-slim

# Prevents Python from writing .pyc files & buffers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

# Install system dependencies for psycopg2 / Postgres
RUN apt-get update \
    && apt-get install -y gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /code/

# Start Gunicorn server (point to your Django project)
CMD ["gunicorn", "-c", "gunicorn.conf.py", "fantasy_project.wsgi:application"]
