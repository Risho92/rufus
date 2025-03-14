"""
Utility functions for Rufus.
"""

import logging
import json
from urllib.parse import urlparse, urljoin
from typing import Set, List, Dict, Any
import os
from uuid import uuid4


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Set up and return a logger with the given name and level.
    
    Args:
        name: Name of the logger
        level: Logging level
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    logger.setLevel(level)
    return logger


def normalize_url(url: str) -> str:
    """
    Normalize a URL by removing fragments.
    
    Args:
        url: URL to normalize
        
    Returns:
        Normalized URL
    """
    parsed = urlparse(url)
    
    # Remove fragment
    url = parsed._replace(fragment='').geturl()
    
    # Remove trailing slash if present
    if url.endswith('/'):
        url = url[:-1]
        
    return url


def save_documents(documents: List[Dict[str, Any]], output_format: str, output_file: str) -> str:
    """
    Save documents to file in specified format.
    
    Args:
        documents: List of documents to save
        output_format: Format to save in ("json" or "text")
        output_file: Base filename (without extension)
        
    Returns:
        Path to saved file
    """
    uuid_tag = str(uuid4())
    output_file_name = output_file + "_" + uuid_tag
    if output_format == "json":
        output_path = f"{output_file_name}.json"
        with open(output_path, 'w') as f:
            json.dump(documents, f, indent=2)
                
    elif output_format == "text":
        output_path = f"{output_file_name}.txt"
        with open(output_path, 'w') as f:
            for doc in documents:
                f.write(f"=== {doc['title']} ===\n\n")
                f.write(doc['content'])
                f.write("\n\n")
                f.write(f"Sources: {', '.join(doc['metadata']['source_urls'])}\n\n")
                f.write("-" * 80 + "\n\n")
    
    else:
        raise ValueError(f"Unsupported output format: {output_format}")
            
    return output_file_name