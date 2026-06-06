"""
Lightweight RAG (Retrieval-Augmented Generation) module.

Loads documents from a local folder, chunks them, embeds with
sentence-transformers, and stores in ChromaDB for semantic retrieval.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import List, Optional

from qwen3.config import Settings

log = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".csv", ".json"}


def _chunk_text(text: str, size: int, overlap: int) -> List[str]:
    """Split text into overlapping chunks by character count."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return [c.strip() for c in chunks if c.strip()]


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


class RAGEngine:
    """Simple RAG pipeline: load docs → chunk → embed → store → query."""

    def __init__(self, cfg: Settings | None = None):
        self._cfg = cfg or Settings()
        self._collection = None
        self._embedder = None
        self._unavailable = False

    def _ensure_ready(self):
        if self._collection is not None:
            return
        if self._unavailable:
            return

        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            log.warning("RAG dependencies missing (%s). Install: pip install chromadb sentence-transformers", exc)
            self._unavailable = True
            return

        log.info("Loading embedding model: %s", self._cfg.embed_model)
        self._embedder = SentenceTransformer(self._cfg.embed_model)

        self._cfg.chroma_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self._cfg.chroma_dir))
        self._collection = client.get_or_create_collection(
            name="knowledge",
            metadata={"hnsw:space": "cosine"},
        )
        log.info(
            "ChromaDB ready at %s (%d docs)",
            self._cfg.chroma_dir,
            self._collection.count(),
        )

    def index_documents(self, directory: Path | None = None) -> int:
        """Read files from *directory*, chunk, embed and upsert into ChromaDB.
        Returns the number of new chunks added."""
        self._ensure_ready()
        directory = directory or self._cfg.knowledge_dir

        if not directory.exists():
            log.warning("Knowledge directory does not exist: %s", directory)
            return 0

        all_ids: list[str] = []
        all_docs: list[str] = []
        all_embeds: list[list[float]] = []
        all_metas: list[dict] = []

        for fpath in sorted(directory.iterdir()):
            if fpath.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            fhash = _file_hash(fpath)
            text = fpath.read_text(encoding="utf-8", errors="ignore")
            chunks = _chunk_text(
                text, self._cfg.chunk_size, self._cfg.chunk_overlap
            )

            for i, chunk in enumerate(chunks):
                doc_id = f"{fpath.stem}_{fhash[:8]}_{i}"
                all_ids.append(doc_id)
                all_docs.append(chunk)
                all_metas.append({"source": fpath.name, "chunk_idx": i})

        if not all_docs:
            log.info("No documents to index in %s", directory)
            return 0

        log.info("Embedding %d chunks …", len(all_docs))
        all_embeds = self._embedder.encode(all_docs).tolist()

        self._collection.upsert(
            ids=all_ids,
            documents=all_docs,
            embeddings=all_embeds,
            metadatas=all_metas,
        )
        log.info("Indexed %d chunks from %s", len(all_docs), directory)
        return len(all_docs)

    def query(self, question: str, top_k: int | None = None) -> List[str]:
        """Return the *top_k* most relevant chunks for *question*."""
        self._ensure_ready()
        top_k = top_k or self._cfg.rag_top_k

        if self._collection is None or self._collection.count() == 0:
            return []

        q_embed = self._embedder.encode([question]).tolist()
        results = self._collection.query(
            query_embeddings=q_embed, n_results=top_k
        )
        docs = results.get("documents", [[]])[0]
        return docs

    def build_rag_prompt(
        self,
        question: str,
        system_prompt: str = "",
        top_k: int | None = None,
    ) -> List[dict]:
        """Build a messages list with retrieved context injected."""
        context_chunks = self.query(question, top_k)

        if context_chunks:
            context_block = "\n---\n".join(context_chunks)
            system_content = (
                f"{system_prompt}\n\n"
                "Dưới đây là thông tin tham khảo được truy xuất tự động. "
                "Hãy dựa vào thông tin này để trả lời chính xác.\n\n"
                f"{context_block}"
            ).strip()
        else:
            system_content = system_prompt or "Bạn là trợ lý AI hữu ích và ngắn gọn."

        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": question},
        ]

    @property
    def doc_count(self) -> int:
        self._ensure_ready()
        if self._collection is None:
            return 0
        return self._collection.count()
