import os
import tempfile
import unittest
from pathlib import Path

from agent.thread_manager import ThreadManager


class TestThreadManagerIsolation(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.db_path = Path(self._tmp.name) / "threads.db"
        os.environ["THREADS_DB_PATH"] = str(self.db_path)

    def tearDown(self) -> None:
        os.environ.pop("THREADS_DB_PATH", None)

    def test_context_is_isolated_by_thread_id(self) -> None:
        manager = ThreadManager()

        manager.append_message("thread_a", role="user", content="Acme just raised a Series B.")
        manager.append_message("thread_b", role="user", content="BetterCo hired a new CTO.")
        manager.append_message("thread_a", role="assistant", content="Noted: funding signal.")

        ctx_a = manager.get_context("thread_a")
        text_a = " ".join(m.content for m in ctx_a)
        self.assertIn("Acme", text_a)
        self.assertIn("funding", text_a)
        self.assertNotIn("BetterCo", text_a)

        ctx_b = manager.get_context("thread_b")
        text_b = " ".join(m.content for m in ctx_b)
        self.assertIn("BetterCo", text_b)
        self.assertNotIn("Acme", text_b)

    def test_clear_thread_only_deletes_that_thread(self) -> None:
        manager = ThreadManager()
        manager.append_message("thread_a", role="user", content="A1")
        manager.append_message("thread_b", role="user", content="B1")

        manager.clear_thread("thread_a")
        self.assertEqual(len(manager.get_context("thread_a")), 0)
        self.assertEqual(len(manager.get_context("thread_b")), 1)


if __name__ == "__main__":
    unittest.main()

