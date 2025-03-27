def setup_logger(lock, log_file='shared.log'):
    import logging

    logger = logging.getLogger(str(id(lock)))  # Unique logger per lock
    logger.setLevel(logging.INFO)

    # Open file in append mode ('a') to prevent overwriting
    handler = logging.FileHandler(log_file, mode='a')  # APPEND mode
    formatter = logging.Formatter('%(asctime)s -  %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    original_emit = handler.emit

    def emit_with_lock(record):
        lock.acquire()
        try:
            original_emit(record)
        finally:
            lock.release()

    handler.emit = emit_with_lock
    logger.addHandler(handler)
    return logger



from multiprocessing import Process, Lock
import time

def worker(token_id, lock):
    logger = setup_logger(lock)
    for i in range(10000):
        logger.info(f"Token {token_id} log {i}")
        time.sleep(0.1)

if __name__ == "__main__":
    log_lock = Lock()
    processes = []
    tokens = [163, 526]

    for t in tokens:
        p = Process(target=worker, args=(t, log_lock))
        p.start()
        processes.append(p)

    for p in processes:
        p.join()

    print("All logging done.")
