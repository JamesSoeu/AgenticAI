FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY orchestrator_router ./orchestrator_router

EXPOSE 8080
CMD ["uvicorn", "orchestrator_router.app:app", "--host", "0.0.0.0", "--port", "8080"]
