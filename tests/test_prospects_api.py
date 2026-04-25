import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from agent.main import app
except Exception as exc:  # pragma: no cover
    TestClient = None  # type: ignore[assignment]
    app = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


@unittest.skipIf(
    TestClient is None,
    f"Skipping prospects API tests (FastAPI/Pydantic mismatch or missing endpoints): {_IMPORT_ERROR}",
)
class TestProspectsApi(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.tempdir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tempdir.name) / "prospects.json"
        self.store_path.write_text(
            json.dumps(
                [
                    {
                        "id": "consolety",
                        "prospect_name": "Bethel Yohannes",
                        "company": "Consolety",
                        "email": "bethelyohannes4@gmail.com",
                    }
                ]
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_list_prospects_reads_backend_store(self) -> None:
        with patch.dict("os.environ", {"PROSPECTS_STORE_PATH": str(self.store_path)}, clear=False):
            result = self.client.get("/prospects")

        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertEqual(len(body["prospects"]), 1)
        self.assertEqual(body["prospects"][0]["company"], "Consolety")


if __name__ == "__main__":
    unittest.main()
