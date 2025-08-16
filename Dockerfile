FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
	gcc \
	postgresql-client \
	&& rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
	&& chown -R app:app /app
USER app

EXPOSE 8000

CMD ["gunicorn", "mess_management.wsgi:application", "--bind", "0.0.0.0:8000"]
