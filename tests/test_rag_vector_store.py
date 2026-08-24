from __future__ import annotations

from langchain_core.documents import Document

from app.engine.rag import LocalChromaVectorStore


class FakeEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text))]


class FakeCollection:
    def __init__(self) -> None:
        self.added: dict | None = None
        self.query_input: dict | None = None

    def add(self, **kwargs: object) -> None:
        self.added = kwargs

    def query(self, **kwargs: object) -> dict:
        self.query_input = kwargs
        return {
            "documents": [["规范片段 A", "规范片段 B"]],
            "metadatas": [[{"chunk_index": 1}, {"chunk_index": 2}]],
        }


def test_local_chroma_adapter_adds_and_retrieves_documents() -> None:
    collection = FakeCollection()
    store = LocalChromaVectorStore(collection=collection, embeddings=FakeEmbeddings())
    documents = [
        Document(page_content="第一条规范", metadata={"chunk_index": 0}),
        Document(page_content="第二条规范", metadata={"chunk_index": 1}),
    ]

    store.add_documents(documents)
    results = store.similarity_search("疏散净宽", k=2)

    assert collection.added == {
        "ids": ["chunk-0", "chunk-1"],
        "documents": ["第一条规范", "第二条规范"],
        "metadatas": [{"chunk_index": 0}, {"chunk_index": 1}],
        "embeddings": [[5.0], [5.0]],
    }
    assert collection.query_input == {"query_embeddings": [[4.0]], "n_results": 2}
    assert [(item.page_content, item.metadata) for item in results] == [
        ("规范片段 A", {"chunk_index": 1}),
        ("规范片段 B", {"chunk_index": 2}),
    ]
