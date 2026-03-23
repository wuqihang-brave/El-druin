FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    streamlit>=1.28.0 \
    plotly>=5.18.0 \
    pandas>=2.1.0 \
    requests>=2.31.0 \
    python-dateutil>=2.8.2 \
    networkx>=3.2.0

COPY . /app

EXPOSE 8501

CMD ["streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
