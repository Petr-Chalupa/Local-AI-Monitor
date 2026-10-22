FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["fastapi", "run", "monitor.py", "--host", "0.0.0.0", "--port", "8080"]