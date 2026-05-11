set -eu

exec gunicorn --bind 0.0.0.0:${APP_PORT:-8080} --workers 1 --threads 8 --timeout 120 'mcm.app:create_app()'
