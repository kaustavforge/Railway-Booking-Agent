"""Re-index railway policy documents with FastEmbed.

This intentionally requires --reset before deleting vectors from the configured
Pinecone index. Run only after confirming PINECONE_INDEX_NAME and the target
project credentials.
"""
import argparse
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
from langchain_pinecone import Pinecone as PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone, ServerlessSpec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Delete all vectors before indexing")
    args = parser.parse_args()
    if not args.reset:
        raise SystemExit("Refusing to delete vectors. Re-run with --reset after verifying the target index.")

    load_dotenv()
    api_key = os.environ["PINECONE_API_KEY"]
    index_name = os.getenv("PINECONE_INDEX_NAME", "railway-refund-policy")
    data_dir = Path(__file__).resolve().parents[1] / "data"
    pdf_path = data_dir / "refund_cancellation_policy.pdf"

    pc = Pinecone(api_key=api_key)
    # Recreate this dedicated policy index to guarantee no old-model vectors
    # remain. Do not use this script for an index containing unrelated data.
    if index_name in pc.list_indexes().names():
        pc.delete_index(index_name)
        while index_name in pc.list_indexes().names():
            time.sleep(1)
    pc.create_index(
        name=index_name,
        dimension=384,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )
    while not pc.describe_index(index_name).status.ready:
        time.sleep(1)

    index = pc.Index(index_name)
    print(f"Recreated Pinecone index: {index_name}")

    embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    vectorstore = PineconeVectorStore(index=index, embedding=embeddings)
    documents = PyPDFLoader(str(pdf_path)).load()
    chunks = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50).split_documents(documents)
    vectorstore.add_documents(chunks)
    print(f"Indexed {len(chunks)} policy chunks with FastEmbed.")


if __name__ == "__main__":
    main()
