import hashlib
import json
import time

MODEL_ID = "google/siglip2-base-patch16-224"
MODEL_REVISION = "75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2"


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
            return (features / features.norm(dim=-1, keepdim=True)).float().cpu().numpy()[0]
