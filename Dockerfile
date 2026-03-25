FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 5000

# Wait for MySQL to be reachable before starting Flask.
CMD ["python", "wait_for_db.py"]
