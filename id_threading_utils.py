# -*- coding: utf-*-
# utilities
import concurrent.futures
import logging
import threading
import time


class Future(object):
    def __init__(self, logger: logging.Logger, executor: concurrent.futures.ThreadPoolExecutor):
        self.__logger: logging.Logger = logger
        self.__executor: concurrent.futures.ThreadPoolExecutor = executor
        # noinspection PyTypeChecker
        self.__delegate: concurrent.futures.Future = None
        # noinspection PyTypeChecker
        self.__timer: threading.Timer = None
        self.__fn = None
        self.__args = None
        self.__kwargs = None

    def cancel(self):
        if self.__timer:
            self.__timer.cancel()
        if self.__delegate:
            self.__delegate.cancel()

    def running(self):
        return self.__delegate and self.__delegate.running()

    def done(self):
        return self.__delegate and self.__delegate.done()

    def cancelled(self):
        return not self.__timer and self.__delegate and self.__delegate.cancelled()

    def result(self, timeout=None):
        remaining: float = timeout
        while not self.__delegate:
            time.sleep(0.1)
            remaining = remaining - 0.1
        if self.__delegate:
            if remaining:
                return self.__delegate.result(round(remaining))
            return self.__delegate.result()
        return None

    def exception(self, timeout=None):
        remaining: float = timeout
        while not self.__delegate:
            time.sleep(0.1)
            remaining = remaining - 0.1
        if self.__delegate:
            if remaining:
                return self.__delegate.exception(round(remaining))
            return self.__delegate.exception()
        return None

    def __submit(self, duration: float):
        if duration <= 0:
            self.__timer = None
        else:
            self.__logger.debug('Rescheduling next execution of %s', self.__fn)
            self.__timer = threading.Timer(duration, self.__submit, [duration])
            self.__timer.start()
        self.__logger.debug('Execution of %s', self.__fn)
        self.__delegate = self.__executor.submit(self.__fn, *self.__args, **self.__kwargs)

    def submit(self, duration: float, fn, *args, **kwargs):
        self.__fn = fn
        self.__args = args
        self.__kwargs = kwargs
        self.__submit(-1)

    def schedule(self, delay: float, fn, *args, **kwargs) -> None:
        self.__fn = fn
        self.__args = args
        self.__kwargs = kwargs
        self.__timer = threading.Timer(delay, self.__submit, [-1])
        self.__timer.start()

    def schedule_at_rate(self, delay: float, duration: float, fn, *args, **kwargs) -> None:
        self.__fn = fn
        self.__args = args
        self.__kwargs = kwargs
        self.__timer = threading.Timer(delay, self.__submit, [duration])
        self.__timer.start()


class Executor(object):
    __logger: logging.Logger = None

    def __init__(self, parent_logger: logging.Logger, thread_name_prefix: str, max_workers: int):
        if not Executor.__logger:
            Executor.__logger = logging.getLogger(self.__class__.__name__)
            for handler in parent_logger.handlers:
                Executor.__logger.addHandler(handler)
            Executor.__logger.setLevel(parent_logger.level)
        Executor.__logger.info('Initializing %s', self.__class__.__name__)
        self.__executor: concurrent.futures.ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=thread_name_prefix)

    def submit(self, fn, *args, **kwargs) -> Future:
        Executor.__logger.debug('Submitting: %s', fn)
        future: Future = Future(Executor.__logger, self.__executor)
        future.submit(-1, fn, *args, **kwargs)
        return future

    def schedule(self, delay: float, fn, *args, **kwargs) -> Future:
        Executor.__logger.debug('Scheduling: %s with delay: %s', fn, str(delay))
        future: Future = Future(Executor.__logger, self.__executor)
        future.schedule(delay, fn, *args, **kwargs)
        return future

    def schedule_at_rate(self, delay: float, duration: float, fn, *args, **kwargs) -> Future:
        Executor.__logger.debug('Scheduling at fixed rate: %s with delay: %s and rate: %s', fn, str(delay), str(duration))
        future: Future = Future(Executor.__logger, self.__executor)
        future.schedule_at_rate(delay, duration, fn, *args, **kwargs)
        return future

    def shutdown(self, wait=True):
        self.__executor.shutdown(wait)
