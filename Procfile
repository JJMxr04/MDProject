web: gunicorn CoreRoot.wsgi --log-file -
worker: celery -A CoreRoot worker --loglevel=info
