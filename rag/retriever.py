import torch
from sentence_transformers import SentenceTransformer

class EmbeddingModel:
    def __init__(self):
        self.model = self.load_model()

    def load_model(self):

        MODEL_ID = "nvidia/Nemotron-3-Embed-1B-BF16"

        model = SentenceTransformer(
            MODEL_ID,
            device="cuda",
            model_kwargs={
                "dtype": torch.bfloat16,
                "attn_implementation": "flash_attention_2",
            },
        )
        model.max_seq_length = 32768

        return model

    def embed_query(self, queries: list):
        return self.model.encode_query(queries, batch_size=2, convert_to_tensor=True)
    
    def embed_document(self, documents: list):
        return self.model.encode_document(documents, batch_size=2, convert_to_tensor=True)

