import time
import uuid

import cv2
import numpy as np
from fastapi.testclient import TestClient

from restoration_worker.server import CONFIG, app


def make_jpeg() -> bytes:
    image = np.zeros((80, 120, 3), dtype=np.uint8)
    image[:, :] = (45, 95, 180)
    cv2.putText(image, "TEST", (10, 48), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 45])
    assert ok
    return encoded.tobytes()


def test_direct_local_image_flow():
    payload = make_jpeg()
    job_id = str(uuid.uuid4())
    headers = {"x-restoration-pairing": CONFIG.pairing_secret}
    with TestClient(app) as client:
        created = client.post("/v1/jobs", headers=headers, json={
            "job_id": job_id, "filename": "low quality.jpg", "size": len(payload),
            "mime": "image/jpeg", "preset": "balanced", "target_height": 720, "options": {},
        })
        assert created.status_code == 200, created.text
        uploaded = client.put(f"/v1/jobs/{job_id}/chunk?offset=0", headers=headers, content=payload)
        assert uploaded.status_code == 200, uploaded.text
        completed = client.post(f"/v1/jobs/{job_id}/complete", headers=headers)
        assert completed.status_code == 200, completed.text
        state = None
        for _ in range(80):
            response = client.get(f"/v1/jobs/{job_id}", headers=headers)
            state = response.json()
            if state["status"] in {"completed", "failed"}:
                break
            time.sleep(0.1)
        assert state and state["status"] == "completed", state
        assert state["output_size"] > 0
        output = client.get(f"/v1/jobs/{job_id}/download", headers=headers)
        assert output.status_code == 200
        assert len(output.content) == state["output_size"]
