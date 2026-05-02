FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for asyncpg and bcrypt
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=2.1.3
RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Configure Poetry: don't create a virtualenv inside the container
ENV POETRY_VIRTUALENVS_CREATE=false

# Copy dependency files first (better Docker layer caching)
COPY pyproject.toml poetry.lock* ./

# Install dependencies (no dev deps in production, but include for dev image)
RUN poetry install --no-interaction --no-ansi

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
