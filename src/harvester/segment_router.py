from typing import Optional


def _get_numpy():
    try:
        import numpy as np
        return np
    except ImportError:
        return None


class SegmentRouter:
    def __init__(
        self,
        embedding_model: str = "BAAI/bge-m3",
        device: str = "cpu",
        similarity_threshold: float = 0.3,
    ):
        self.embedding_model = embedding_model
        self.device = device
        self.similarity_threshold = similarity_threshold
        self._model = None
        self._embedding_dim = 1024
        self._np = _get_numpy()

    def load_model(self):
        if not self._np:
            print("[WARN] numpy not available, skipping embedding model load")
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.embedding_model, device=self.device)
            print(f"[INFO] Loaded embedding model: {self.embedding_model}")
        except Exception as e:
            print(f"[WARN] Could not load embedding model: {e}")
            self._model = None

    def route(self, chunks: list[dict], criteria: list[dict]) -> list[dict]:
        if not self._model or not self._np:
            return self._route_fallback(chunks, criteria)

        chunk_texts = [c.get("text", "") for c in chunks]
        criterion_texts = [
            f"{cr.get('label', '')} {', '.join(cr.get('canonical_entities', []))}"
            for cr in criteria
        ]

        chunk_embeddings = self._model.encode(chunk_texts, normalize_embeddings=True)
        criterion_embeddings = self._model.encode(criterion_texts, normalize_embeddings=True)

        similarity_matrix = self._np.dot(chunk_embeddings, criterion_embeddings.T)

        assignments = []
        for i, chunk in enumerate(chunks):
            best_match_idx = self._np.argmax(similarity_matrix[i])
            best_score = similarity_matrix[i][best_match_idx]

            if best_score >= self.similarity_threshold:
                assignments.append({
                    "chunk_id": chunk.get("chunk_id", f"chunk-{i}"),
                    "criterion_id": criteria[best_match_idx].get("criterion_id", ""),
                    "criterion_label": criteria[best_match_idx].get("label", ""),
                    "similarity_score": float(best_score),
                })

        return assignments

    def _route_fallback(self, chunks: list[dict], criteria: list[dict]) -> list[dict]:
        assignments = []
        for i, chunk in enumerate(chunks):
            chunk_text = chunk.get("text", "").lower()
            for cr in criteria:
                criterion_text = (
                    cr.get("label", "") + " " + " ".join(cr.get("canonical_entities", []))
                ).lower()
                if any(entity in chunk_text for entity in cr.get("canonical_entities", [])):
                    assignments.append({
                        "chunk_id": chunk.get("chunk_id", f"chunk-{i}"),
                        "criterion_id": cr.get("criterion_id", ""),
                        "criterion_label": cr.get("label", ""),
                        "similarity_score": 0.5,
                    })
        return assignments

    def compute_similarity(self, text1: str, text2: str) -> float:
        if not self._model or not self._np:
            return self._keyword_similarity(text1, text2)

        embeddings = self._model.encode([text1, text2], normalize_embeddings=True)
        similarity = self._np.dot(embeddings[0], embeddings[1])
        return float(similarity)

    def _keyword_similarity(self, text1: str, text2: str) -> float:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    def get_relevant_chunks(self, chunks: list[dict], criterion: dict, top_k: int = 5) -> list[dict]:
        if not chunks:
            return []

        criterion_text = (
            f"{criterion.get('label', '')} {', '.join(criterion.get('canonical_entities', []))}"
        )

        for chunk in chunks:
            chunk["text"] = chunk.get("text", "")

        if self._model and self._np:
            chunk_texts = [c.get("text", "") for c in chunks]
            chunk_embeddings = self._model.encode(chunk_texts, normalize_embeddings=True)
            criterion_embeddings = self._model.encode([criterion_text], normalize_embeddings=True)
            scores = self._np.dot(chunk_embeddings, criterion_embeddings[0])
            for i, chunk in enumerate(chunks):
                chunk["relevance_score"] = float(scores[i])
        else:
            for chunk in chunks:
                chunk["relevance_score"] = self._keyword_similarity(
                    chunk.get("text", ""), criterion_text
                )

        sorted_chunks = sorted(chunks, key=lambda x: x.get("relevance_score", 0), reverse=True)
        return sorted_chunks[:top_k]