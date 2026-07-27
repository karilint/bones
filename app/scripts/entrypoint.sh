#!/bin/sh
set -e

echo "Checking SQL Server connection"
python manage.py shell < ./scripts/check_db_connection.py

echo "Applying database migrations"
python manage.py migrate --no-input

if [ "${INITIALIZE_APP:-0}" = "1" ]; then
    echo "Initializing application data"
    python manage.py shell < ./scripts/initialize.py
fi

echo "Starting Django development server"
exec python manage.py runserver 0.0.0.0:8000
