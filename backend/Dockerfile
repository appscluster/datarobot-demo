FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY agent /app/agent
COPY backend /app/backend
COPY data /app/data
ENV PYTHONPATH=/app
EXPOSE 54123
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "54123"]
