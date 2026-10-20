from types import SimpleNamespace

import numpy as np
import pytest

from nyx.perception import SiglipEncoder


@pytest.mark.parametrize("structured", [False, True])
def test_siglip_normalizes_image_and_text_pooling_across_transformers_versions(structured):
    import torch

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
