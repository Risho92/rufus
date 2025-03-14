import openai
from typing import List, Dict, Any, Optional
import logging
import json

from .crawler import WebCrawler
from .synthesizer import DocumentSynthesizer
from .models import Document, CrawlStrategy
from .utils import setup_logger, save_documents


class RufusClient:
    """Main client interface for Rufus."""
    
    def __init__(self, api_key: str, max_pages: int = 30, concurrency: int = 5, max_depth: int = 3, 
                 min_relevance: float = 0.3, output_format: str = "json", output_file: str = "rufus_documents"):
        """
        Initialize the Rufus client.
        
        Args:
            api_key: API key for LLM access
            max_pages: Maximum number of pages to crawl
            concurrency: Number of concurrent requests
        """
        self.api_key = api_key
        self.max_pages = max_pages
        self.concurrency = concurrency
        self.max_depth = max_depth
        self.min_relevance = min_relevance
        self.output_format = output_format
        self.output_file = output_file
        
        # Initialize OpenAI client
        self.llm_client = openai.OpenAI(api_key=api_key)
        
        # Initialize components
        self.crawler = WebCrawler(self.llm_client, max_pages, concurrency, max_depth, min_relevance)
        self.synthesizer = DocumentSynthesizer(self.llm_client)
        
        # Set up logging
        self.logger = setup_logger("Rufus")
    
    def scrape(self, start_url: str, instructions: str = None) -> List[Dict[str, Any]]:
        """
        Scrape content from a website based on user instructions.
        
        Args:
            start_url: The starting URL for crawling
            instructions: User instructions for guiding the crawl
            
        Returns:
            List of structured documents as dictionaries
        """
        self.logger.info(f"Starting scrape of {start_url} with instructions: {instructions}")
        
        # Create crawling strategy based on instructions
        strategy = self.crawler.create_crawl_strategy(start_url, instructions)
        
        # Execute the crawl
        crawl_results = self.crawler.crawl(start_url, strategy)
        
        if not crawl_results:
            self.logger.warning("No relevant content found during crawl")
            return []
        
        # Synthesize documents from results
        documents = self.synthesizer.synthesize(crawl_results, instructions)
        
        # Convert to dictionaries for return
        document_dicts = [doc.to_dict() for doc in documents]
        
        self.logger.info(f"Scrape complete. Created {len(documents)} documents")
        return document_dicts
    
    def save_documents(self, documents: List[Dict[str, Any]]) -> str:
        """
        Save documents to file in specified format.
        
        Args:
            documents: List of documents to save
            output_format: Format to save in ("json" or "text")
            output_file: Base filename (without extension)
            
        Returns:
            Path to saved file
        """
        return save_documents(documents, self.output_format, self.output_file)