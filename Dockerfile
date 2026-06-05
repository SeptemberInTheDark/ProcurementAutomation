FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/app

COPY requirements.txt /srv/app/
RUN pip install --no-cache-dir -r requirements.txt

COPY app /srv/app/app
COPY data /srv/app/data

WORKDIR /srv/app/app

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
