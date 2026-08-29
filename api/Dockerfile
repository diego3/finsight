FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Dev overrides this with runserver (see docker-compose.yml). Production runs
# it as-is via docker-compose.prod.yml.
CMD ["gunicorn", "-c", "gunicorn.conf.py", "config.wsgi:application"]
