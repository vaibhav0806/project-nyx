MODEL_ID = "google/siglip2-base-patch16-224"
MODEL_REVISION = "75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2"


def compatible_fingerprints(left, right):
    """Accept only the measured metadata-only SigLIP processor transition."""
    if left == right:
        return True
    # Transformers 5 omits _processor_class from image_processor.to_dict().
    # Pixels, tokens and embeddings were compared with the locked v4 runtime.
    # Keep this allowlist exact: other preprocessing changes require reindexing.
    signatures = {
        "88acf431ff7614d8b483901a6081638db423762041c19387afbbcf820d43636b",
        "78fc613b813e1657e1aecca76714a7c9be8548da1ee749d678c68c58754148bc",
    }
    return (
        set(left) == set(right) == {"model", "revision", "preprocessing"}
        and left["model"] == right["model"] == MODEL_ID
        and left["revision"] == right["revision"] == MODEL_REVISION
        and left["preprocessing"] in signatures
        and right["preprocessing"] in signatures
    )


class CloudEncoder:
    def __init__(self, client=None):
        import os

        from nyx.cloud import OpenRouter

        self.client = client or OpenRouter()
        self.model = os.environ.get("NYX_EMBEDDING_MODEL", "google/gemini-embedding-2")
        self.dimensions = int(os.environ.get("NYX_EMBEDDING_DIMENSIONS", "768"))
        if not 1 <= self.dimensions <= 4096:
            raise ValueError("Embedding dimensions must be between 1 and 4096")
        self.device = "cloud"
        self.load_seconds = 0
        from collections import OrderedDict
        from threading import Lock

        self.text_cache = OrderedDict()
        self.text_lock = Lock()
        self.fingerprint = {
            "model": self.model,
            "dimensions": self.dimensions,
            "preprocessing": "rgb-jpeg90-768-v1",
            "runtime": "openrouter",
        }

    def _encode(self, inputs):
        import numpy as np

        from nyx.cloud import CloudError

        if not inputs:
            return np.empty((0, self.dimensions), dtype=np.float32)
        result = self.client.request(
            "embeddings",
            {
                "model": self.model,
                "input": inputs,
                "dimensions": self.dimensions,
                "encoding_format": "float",
            },
        )
        try:
            rows = sorted(result["data"], key=lambda row: row["index"])
            if [r["index"] for r in rows] != list(range(len(inputs))):
                raise ValueError
            vectors = np.asarray([row["embedding"] for row in rows], dtype=np.float32)
            if vectors.shape != (len(inputs), self.dimensions) or not np.isfinite(vectors).all():
                raise ValueError
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            if not np.isfinite(norms).all() or (norms == 0).any():
                raise ValueError
            return vectors / norms
        except (KeyError, TypeError, ValueError):
            raise CloudError("Cloud embeddings were invalid; the index was not updated.") from None

    def encode_images(self, images):
        from nyx.cloud import image_part

        return self._encode([{"content": [image_part(image)]} for image in images])

    def encode_text(self, query):
        query = query.strip()
        with self.text_lock:
            if query in self.text_cache:
                self.text_cache.move_to_end(query)
                return self.text_cache[query].copy()
            vector = self._encode([{"content": [{"type": "text", "text": query}]}])[0]
            self.text_cache[query] = vector.copy()
            if len(self.text_cache) > 64:
                self.text_cache.popitem(last=False)
            return vector
