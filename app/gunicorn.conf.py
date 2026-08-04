import multiprocessing
import os

bind = '0.0.0.0:8000'
workers = multiprocessing.cpu_count() * 2 + 1
# Full reconciliation exports parse every selected field log. Keep the worker
# deadline configurable and safely above the measured all-years runtime.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "600"))
