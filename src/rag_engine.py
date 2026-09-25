import os
import glob
import json
from typing import List, Dict, Any, Optional
from langchain_chroma import Chroma
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_core.documents import Document

CHROMA_PERSIST_DIR = os.path.join("data", "chroma_db")
SOURCE_DOCS_DIR = os.path.join("data", "rag_source_docs")

# Local ONNX-based embedding model (BAAI/bge-small-en-v1.5)
embedding_function = FastEmbedEmbeddings(
    model_name="BAAI/bge-small-en-v1.5"
)

def load_all_statutory_sources() -> List[Document]:
    """Reads all JSON files from data/rag_source_docs and converts to LangChain Documents."""
    documents = []
    json_files = glob.glob(os.path.join(SOURCE_DOCS_DIR, "*.json"))
    
    if not json_files:
        print(f"[Warning] No statutory JSON documents found in {SOURCE_DOCS_DIR}")
        return documents

    for filepath in json_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                clauses: List[Dict[str, Any]] = json.load(f)
                for item in clauses:
                    text_content = item.get("statutory_text", "")
                    metadata = {
                        "clause_id": item.get("clause_id", ""),
                        "source_doc": item.get("source_doc", ""),
                        "chapter": item.get("chapter", ""),
                        "topic_tag": item.get("topic_tag", "")
                    }
                    doc = Document(page_content=text_content, metadata=metadata)
                    documents.append(doc)
        except Exception as e:
            print(f"[Error] Failed to read {filepath}: {e}")

    return documents

def build_or_get_vector_store() -> Chroma:
    """Initializes or loads persistent ChromaDB vector store."""
    os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
    
    vector_store = Chroma(
        collection_name="irdai_statutory_rules",
        embedding_function=embedding_function,
        persist_directory=CHROMA_PERSIST_DIR
    )
    
    # Ingest if collection is empty
    existing_count = vector_store._collection.count()
    if existing_count == 0:
        docs = load_all_statutory_sources()
        if docs:
            print(f"[RAG] Indexing {len(docs)} verified statutory clauses into ChromaDB...")
            vector_store.add_documents(docs)
            print("[RAG] Vector database successfully indexed!")
    
    return vector_store

def retrieve_regulatory_clauses_for_topics(topics: List[str], top_k_per_topic: int = 2) -> str:
    """
    Precision retrieval: Uses topic_tags supplied directly by the Rules Engine.
    Falls back to semantic search if a topic has no exact match.
    """
    vector_store = build_or_get_vector_store()
    retrieved_docs: List[Document] = []
    seen_clause_ids = set()

    for topic in topics:
        # First attempt metadata filter by topic_tag
        results = vector_store.similarity_search(
            query=topic.replace("_", " "),
            k=top_k_per_topic,
            filter={"topic_tag": topic} if topic else None
        )
        
        # If filtered search returns nothing, perform open semantic search
        if not results:
            results = vector_store.similarity_search(query=topic.replace("_", " "), k=top_k_per_topic)

        for doc in results:
            clause_id = doc.metadata.get("clause_id")
            if clause_id not in seen_clause_ids:
                seen_clause_ids.add(clause_id)
                retrieved_docs.append(doc)

    if not retrieved_docs:
        # General default fallback retrieval
        retrieved_docs = vector_store.similarity_search(query="zero depreciation glass repair standard claims", k=3)

    formatted_context = []
    for doc in retrieved_docs:
        meta = doc.metadata
        formatted_context.append(
            f"[{meta.get('clause_id')}] Source: {meta.get('source_doc')} | Chapter: {meta.get('chapter')}\n"
            f"Rule: {doc.page_content}\n"
        )

    return "\n".join(formatted_context)