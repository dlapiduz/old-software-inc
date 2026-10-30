FROM python:2.7.18-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ORDERDESK_ENV=production \
    ORDERDESK_DB=sqlite:////data/orderdesk.db

WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY . .
RUN mkdir -p /data
VOLUME /data
EXPOSE 5000

CMD ["sh", "-c", "python manage.py seed --if-empty && python manage.py runserver --host 0.0.0.0 --port 5000"]
