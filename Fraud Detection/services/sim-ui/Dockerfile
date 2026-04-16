FROM python:3.10-slim

WORKDIR /app

COPY services/sim-ui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/sim-ui/app.py .
COPY services/sim-ui/index.html .

EXPOSE 8050

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8050"]
