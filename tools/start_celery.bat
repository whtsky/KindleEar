cd /d "%~dp0.."
rem celery -A main.celery_app worker --loglevel=info --concurrency=2 -P eventlet
celery -A main.celery_app worker --loglevel=info --logfile=d:\celery.log --concurrency=2 -P eventlet
