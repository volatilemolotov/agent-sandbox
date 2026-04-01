FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

# Tell Playwright where the browsers actually live in this base image
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install the API dependencies AND the Python Playwright bindings
RUN pip install fastapi uvicorn pydantic playwright

# Copy the server AND your search tool
COPY server.py .
COPY search.py .

RUN chown -R 1000:1000 /app
USER 1000

# Expose the port that the Uvicorn server will run on
EXPOSE 8888

# Start the Uvicorn server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8888", "--log-level", "trace"]
