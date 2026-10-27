from types import SimpleNamespace

import numpy as np
import pytest

from nyx.perception import SiglipEncoder


@pytest.mark.parametrize("structured", [False, True])
def test_siglip_normalizes_image_and_text_pooling_across_transformers_versions(structured):
    torch = pytest.importorskip("torch", reason="Requires the optional vision extra")

    class Inputs(dict):
        def to(self, device):
            return self

    def features(**kwargs):
        tensor = torch.tensor([[3.0, 4.0]])
        return SimpleNamespace(pooler_output=tensor) if structured else tensor

    encoder = SiglipEncoder.__new__(SiglipEncoder)
    encoder.device = "cpu"
    encoder.processor = lambda **kwargs: Inputs()
    encoder.model = SimpleNamespace(get_image_features=features, get_text_features=features)
    np.testing.assert_allclose(encoder.encode_images([object()]), [[0.6, 0.8]])
    np.testing.assert_allclose(encoder.encode_text("remote"), [0.6, 0.8])


def test_measured_processor_metadata_transition_preserves_saved_index(tmp_path):
    import json

    from nyx.memory import Store
    from nyx.perception import MODEL_ID, MODEL_REVISION, compatible_fingerprints
    from nyx.retrieval import search

    old = {
        "model": MODEL_ID,
        "revision": MODEL_REVISION,
        "preprocessing": "88acf431ff7614d8b483901a6081638db423762041c19387afbbcf820d43636b",
    }
    new = {
        **old,
        "preprocessing": "78fc613b813e1657e1aecca76714a7c9be8548da1ee749d678c68c58754148bc",
    }
    original = Store(tmp_path, old, 3)
    video = original.add_video("test.mp4", "test.mp4", "2026-10-20T10:00:00Z", 2)
    original.add_frames(video, [(2, "test.jpg")], [[1, 0, 0]])
    original.finish_video(video)
    reopened = Store(tmp_path, new, 3)
    encoder = SimpleNamespace(fingerprint=new, dimensions=3, encode_text=lambda _: [1, 0, 0])
    assert search("item", reopened, encoder)[0]["observed_at"] == "2026-10-20T10:00:02+00:00"
    # Metadata-only reads also return the original fingerprint; search must accept it.
    assert search("item", original, encoder)[0]["video_id"] == video
    with reopened.connection() as db:
        identity = json.loads(
            db.execute("SELECT value FROM meta WHERE key='encoder'").fetchone()[0]
        )
    assert identity["encoder"] == old  # Preserve rollback identity and vectors.
    assert Store(tmp_path, old, 3).search([1, 0, 0])[0]["video_id"] == video
    for key in ("model", "revision", "preprocessing"):
        changed = {**new, key: "unmeasured"}
        assert not compatible_fingerprints(old, changed)
        with pytest.raises(ValueError, match="different encoder"):
            Store(tmp_path, changed, 3)
    assert not compatible_fingerprints(old, {**new, "extra": "unknown"})
    with pytest.raises(ValueError, match="different encoder"):
        Store(tmp_path, new, 4)
