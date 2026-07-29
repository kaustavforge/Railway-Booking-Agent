"""
Complaint filing tool.
"""

from langchain_core.tools import tool


@tool
def file_complaint(category: str, description: str) -> str:
    """File a customer complaint."""
    raise NotImplementedError("Handled by complaint_approval_node instead.")
