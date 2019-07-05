from threading import Lock


class MutexLock:
    def __init__(self, lock: Lock):
        self.__lock = lock

    def __enter__(self):
        self.__lock.acquire(blocking=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.__lock.release()
        except:
            pass
