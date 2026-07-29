"""
Refund/cancellation policy RAG tool.
"""

from langchain_core.tools import tool

from app.config.settings import policy_vectorstore


@tool
def search_refund_policy(query: str) -> str:
    """Search the refund/cancellation policy document using Pinecone RAG."""
    results = policy_vectorstore.similarity_search(query, k=2)
    if not results:
        return "No relevant policy information found. Try rephrasing your question."
    return "\n\n---\n\n".join(r.page_content.strip() for r in results)
