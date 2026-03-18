FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV AGENT_LOG_PATH=/app/agent_log.json

CMD ["python", "main.py"]
