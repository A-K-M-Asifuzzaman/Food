"""Build the hybrid retrieval index: a LangChain vector store plus the document rows."""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_huggingface import HuggingFaceEmbeddings

from nutrivision.config import DATA_DIR, INDEX_DIR

CORPUS_PATH = DATA_DIR / "nutrition" / "corpus.jsonl"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

VECTORSTORE_NAME = "vectorstore.json"
DOCUMENTS_NAME = "documents.jsonl"
MANIFEST_NAME = "manifest.json"

QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class BgeEmbeddings(HuggingFaceEmbeddings):
    """HuggingFaceEmbeddings carrying the bge query-side instruction."""

    def embed_query(self, text: str) -> list[float]:
        return super().embed_query(QUERY_INSTRUCTION + text)


def get_embeddings(model_name: str = EMBED_MODEL, show_progress: bool = False) -> BgeEmbeddings:
    return BgeEmbeddings(
        model_name=model_name,
        encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
        show_progress=show_progress,
    )


@dataclass
class CorpusRow:
    """One line of the corpus, before it becomes a LangChain document."""

    doc_id: str
    kind: str
    text: str
    food_class: str | None
    title: str
    metadata: dict

    def as_document(self) -> Document:
        return Document(
            id=self.doc_id,
            page_content=self.text,
            metadata={
                "doc_id": self.doc_id,
                "kind": self.kind,
                "title": self.title,
                "food_class": self.food_class,
                "attributes": self.metadata,
            },
        )


def load_corpus(path=CORPUS_PATH) -> list[CorpusRow]:
    rows = []
    with open(path) as fh:
        for line in fh:
            row = json.loads(line)
            rows.append(
                CorpusRow(
                    doc_id=row["doc_id"],
                    kind=row["kind"],
                    text=row["text"],
                    food_class=row["food_class"],
                    title=row["title"],
                    metadata=row.get("metadata", {}),
                )
            )
    return rows


def load_documents(path: Path | None = None) -> list[Document]:
    """The indexed documents, as LangChain documents."""
    path = path or INDEX_DIR / DOCUMENTS_NAME
    with open(path) as fh:
        return [CorpusRow(**json.loads(line)).as_document() for line in fh]


_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens, keeping numbers."""
    return _TOKEN.findall(text.lower())


def build(out_dir=INDEX_DIR, model_name: str = EMBED_MODEL) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    rows = load_corpus()

    from .graph import load_graph

    rows.extend(CorpusRow(**d) for d in load_graph().as_documents())
    documents = [r.as_document() for r in rows]

    store = InMemoryVectorStore(get_embeddings(model_name, show_progress=True))
    store.add_documents(documents)
    store.dump(str(out_dir / VECTORSTORE_NAME))

    with open(out_dir / DOCUMENTS_NAME, "w") as fh:
        for row in rows:
            fh.write(json.dumps(row.__dict__) + "\n")

    for stale in ("bm25.pkl", "embeddings.npy"):
        (out_dir / stale).unlink(missing_ok=True)

    manifest = {
        "documents": len(documents),
        "embed_model": model_name,
        "dim": len(store.store[documents[0].id]["vector"]),
        "kinds": sorted({r.kind for r in rows}),
        "seconds": round(time.time() - started, 2),
    }
    (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    p = argparse.ArgumentParser(description="Build the hybrid retrieval index")
    p.add_argument("--model", default=EMBED_MODEL)
    args = p.parse_args()

    manifest = build(model_name=args.model)
    print(json.dumps(manifest, indent=2))
    print(f"\nwrote {INDEX_DIR}")


if __name__ == "__main__":
    main()
