import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gthread"
threads = 4
timeout = 120
preload_app = True
loglevel = "info"
accesslog = "-"
errorlog = "-"