FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ndvi_monitor ./ndvi_monitor
COPY sample_data ./sample_data
RUN useradd -m app
USER app
EXPOSE 8000
CMD ["uvicorn", "ndvi_monitor.api:app", "--host", "0.0.0.0", "--port", "8000"]
