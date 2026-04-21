from dataclasses import dataclass

@dataclass
class Chunk:
    text: str
    source: str        # document path or URL
    section: str       # heading or section title
    relevance: float   # 0.0 - 1.0

class RAGPipeline:
    """Production RAG with query rewriting and hybrid search."""

    def __init__(self, llm, vector_db, keyword_index,
                 top_k: int = 10, final_k: int = 5):
        self.llm = llm
        self.vector_db = vector_db
        self.keyword_index = keyword_index
        self.top_k = top_k
        self.final_k = final_k

    def query(self, question: str) -> str:  #A
        """Full RAG pipeline: rewrite → retrieve → rerank → generate."""
        rewritten = self.llm.generate(
            f"Rewrite this query to improve search retrieval. "
            f"Add synonyms and related terms. "
            f"Return only the rewritten query.\n\n"
            f"Original: {question}"
        )

        # Hybrid search: semantic + keyword  #B
        semantic = self.vector_db.search(rewritten, top_k=self.top_k)
        keyword = self.keyword_index.search(question, top_k=self.top_k)
        merged = self._rrf_merge(semantic, keyword)

        top_chunks = merged[:self.final_k]

        # Generate with retrieved context  #C
        context = "\n\n".join(
            f"[Source: {c.source}]\n{c.text}"
            for c in top_chunks
        )
        return self.llm.generate(
            f"Answer using ONLY the provided context. "
            f"Cite sources. If the answer isn't in the context, say so.\n\n"
            f"Context:\n{context}\n\nQuestion: {question}"
        )

    def _rrf_merge(  #D
            self, list_a: list[Chunk],
            list_b: list[Chunk],
    ) -> list[Chunk]:
        """Reciprocal Rank Fusion merge of two result sets."""
        scores: dict[str, float] = {}
        chunks: dict[str, Chunk] = {}
        k = 60  # RRF constant
        for rank, chunk in enumerate(list_a):
            key = chunk.source + chunk.text[:100]
            scores[key] = scores.get(key, 0) + 1.0 / (k + rank)
            chunks[key] = chunk
        for rank, chunk in enumerate(list_b):
            key = chunk.source + chunk.text[:100]
            scores[key] = scores.get(key, 0) + 1.0 / (k + rank)
            if key not in chunks:
                chunks[key] = chunk
        ranked = sorted(scores, key=lambda x: -scores[x])
        return [chunks[key] for key in ranked if key in chunks]
