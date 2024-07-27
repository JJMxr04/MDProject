web: gunicorn CoreRoot.wsgi --log-file -
worker: celery -A CoreRoot worker --loglevel=info
beat: celery -A CoreRoot beat --loglevel=info
