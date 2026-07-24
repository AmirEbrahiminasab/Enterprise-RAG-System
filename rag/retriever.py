import torch
from sentence_transformers import SentenceTransformer


class EmbeddingModel:
    def __init__(self):
        self.model = self.load_model()

    def load_model(self):

        MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"

        model = SentenceTransformer(
            MODEL_ID,
            device="cuda",
            model_kwargs={
                "dtype": torch.bfloat16,
                "attn_implementation": "sdpa",
            },
        )
        model.max_seq_length = 1000

        return model

    def embed(self, sentences: list):
        return self.model.encode(sentences, batch_size=4, convert_to_tensor=True)
