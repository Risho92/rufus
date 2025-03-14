"""
Data models for Rufus.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time


@dataclass
class CrawlResult:
    """Represents the result of crawling and processing a single URL."""
    url: str
    content: str
    title: str
    relevance_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawlStrategy:
    """Strategy for crawling a website based on user instructions."""
    keywords: List[str] = field(default_factory=list)
    content_types: List[str] = field(default_factory=lambda: ["all"])
    task: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrawlStrategy":
        """Create a CrawlStrategy from a dictionary."""
        return cls(
            keywords=data.get("keywords", []),
            content_types=data.get("content_types", ["all"]),
            task=data.get("task", "")
        )


@dataclass
class Document:
    """Represents a synthesized document for RAG systems."""
    type: str
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata
        }
    
    @classmethod
    def create(cls, type_: str, title: str, content: str, 
              source_urls: List[str], instruction_prompt: Optional[str] = None) -> "Document":
        """Create a new document with standard metadata."""
        return cls(
            type=type_,
            title=title,
            content=content,
            metadata={
                "source_urls": source_urls,
                "creation_time": time.time(),
                "instruction_prompt": instruction_prompt
            }
        )