FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY data_a2a_agent ./data_a2a_agent

EXPOSE 8080
CMD ["uvicorn", "data_a2a_agent.agent:a2a_app", "--host", "0.0.0.0", "--port", "8080"]
