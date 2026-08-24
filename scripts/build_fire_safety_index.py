from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import settings
from app.engine.rag import build_fire_safety_vector_store


def main() -> None:
    vector_store = build_fire_safety_vector_store(
        rules_path=settings.fire_safety_rules_path,
        persist_dir=settings.chroma_dir,
        embedding_model_name=settings.embedding_model_name,
    )
    collection_size = vector_store._collection.count()  # type: ignore[attr-defined]
    print("Fire safety vector store is ready.")
    print(f"Rules file: {settings.fire_safety_rules_path}")
    print(f"Persist dir: {settings.chroma_dir}")
    print(f"Collection size: {collection_size}")


if __name__ == "__main__":
    main()
