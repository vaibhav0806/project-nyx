import hashlib
import json
import time

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


class SiglipEncoder:
    def __init__(self, device="auto"):
        import torch
        from transformers import AutoModel, AutoProcessor

        started = time.perf_counter()
        if device == "auto":
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        if device == "mps" and not torch.backends.mps.is_available():
            raise ValueError("Apple MPS is unavailable; select --device cpu")
        self.device = device
        self.processor = AutoProcessor.from_pretrained(
            MODEL_ID, revision=MODEL_REVISION, token=False, trust_remote_code=False, use_fast=False
        )
        self.model = (
            AutoModel.from_pretrained(
                MODEL_ID,
                revision=MODEL_REVISION,
                token=False,
                trust_remote_code=False,
                use_safetensors=True,
            )
            .eval()
            .to(device)
        )
        self.dimensions = self.model.config.vision_config.hidden_size
        preprocessing = {
            "image": self.processor.image_processor.to_dict(),
            "text_padding": "max_length",
            "text_length": 64,
            "text_template": "This is a photo of {query}.",
            "tokenizer": type(self.processor.tokenizer).__name__,
            "image_mode": "RGB",
        }
        self.fingerprint = {
            "model": MODEL_ID,
            "revision": MODEL_REVISION,
            "preprocessing": hashlib.sha256(
                json.dumps(preprocessing, sort_keys=True).encode()
            ).hexdigest(),
        }
        self.load_seconds = time.perf_counter() - started

    def encode_images(self, images):
        import torch

        inputs = self.processor(images=images, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            features = self.model.get_image_features(**inputs)
            features = getattr(features, "pooler_output", features)
            return (features / features.norm(dim=-1, keepdim=True)).float().cpu().numpy()

    def encode_text(self, query):
        import torch

        inputs = self.processor(
            text=[f"This is a photo of {query}."],
            padding="max_length",
            max_length=64,
            truncation=True,
            return_tensors="pt",
        ).to(self.device)
        with torch.inference_mode():
            features = self.model.get_text_features(**inputs)
            features = getattr(features, "pooler_output", features)
            return (features / features.norm(dim=-1, keepdim=True)).float().cpu().numpy()[0]
