import multiprocessing as mp
import queue
import threading
import time
import unittest


class SlowPayload:
    """Queue feeder 직렬화가 producer의 put 반환보다 늦는 상황을 재현한다."""

    def __reduce__(self):
        time.sleep(0.5)
        return dict, ()


def old_event_worker(work_queue, finished_adding, processed):
    while True:
        try:
            work_queue.get(timeout=0.1)
        except queue.Empty:
            if finished_adding.is_set():
                break
            continue
        processed.append(1)


def sentinel_worker(work_queue, processed):
    while True:
        item = work_queue.get()
        if item is None:
            break
        processed.append(1)


class MfaExportQueueRaceTests(unittest.TestCase):
    def test_fixed_delay_event_can_drop_delayed_feeder_item(self):
        work_queue = mp.Queue()
        finished = threading.Event()
        processed = []
        worker = threading.Thread(
            target=old_event_worker,
            args=(work_queue, finished, processed),
        )
        worker.start()
        work_queue.put(SlowPayload())
        finished.set()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(processed, [])
        work_queue.close()
        work_queue.join_thread()

    def test_sentinel_waits_until_delayed_feeder_item_is_consumed(self):
        work_queue = mp.Queue()
        processed = []
        worker = threading.Thread(
            target=sentinel_worker,
            args=(work_queue, processed),
        )
        worker.start()
        work_queue.put(SlowPayload())
        work_queue.put(None)
        worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(processed, [1])
        work_queue.close()
        work_queue.join_thread()


if __name__ == "__main__":
    unittest.main()
