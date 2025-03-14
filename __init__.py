"""
Rufus - Intelligent Web Data Extraction Tool for RAG Systems

Rufus is a tool designed to intelligently crawl websites based on user instructions,
extracting and synthesizing data into structured documents for use in 
Retrieval-Augmented Generation (RAG) systems.
"""

__version__ = "0.1.0"

from .client import RufusClient

__all__ = ["RufusClient"]