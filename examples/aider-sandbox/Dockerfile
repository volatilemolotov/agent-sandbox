FROM python:3.11-slim

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir aider-chat[browser]

EXPOSE 8501

ENV STREAMLIT_SERVER_ADDRESS="0.0.0.0"
ENV STREAMLIT_SERVER_PORT="8501"
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS="false"

WORKDIR /workspace

CMD ["aider", "--browser"]
