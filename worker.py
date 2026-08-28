import sys
from worker_config import redis_conn
from rq import Worker, Queue

# Windows doesn't support os.fork() — use SimpleWorker which runs jobs
# in the same process instead of forking a child process.
if sys.platform == "win32":
    from rq.worker import SimpleWorker as WorkerClass
else:
    WorkerClass = Worker

worker = WorkerClass(
    [Queue("click_queue", connection=redis_conn)],
    connection=redis_conn
)

worker.work(with_scheduler=False)