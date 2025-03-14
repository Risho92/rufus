"""
Document synthesis functionality for Rufus.
"""

from typing import List, Dict, Any
import time
from itertools import groupby
from operator import attrgetter

from .models import CrawlResult, Document


class DocumentSynthesizer:
    """Synthesizes crawl results into structured documents for RAG."""
    
    def __init__(self, llm_client: Any):
        """
        Initialize the document synthesizer.
        
        Args:
            llm_client: Client for LLM API access
        """
        self.llm_client = llm_client
    
    def synthesize(self, results: List[CrawlResult], instructions: str) -> List[Document]:
        """
        Synthesize crawl results into structured documents for RAG.
        
        Args:
            results: List of crawl results
            instructions: Original user instructions
            
        Returns:
            List of Document objects
        """
        if not results:
            return []
            
        # Group results by content type
        results_by_type = self._group_by_content_type(results)
        
        documents = []
        
        # Create a document for each content type with high relevance
        for content_type, results_group in results_by_type.items():
            if not results_group:
                continue
                
            # Pick top results from this group
            top_results = self._select_top_results(results_group)
            
            # If we have enough content, synthesize it
            if top_results:
                document = self._create_document(content_type, top_results, instructions)
                documents.append(document)
            
        return documents
    
    def _group_by_content_type(self, results: List[CrawlResult]) -> Dict[str, List[CrawlResult]]:
        """
        Group results by content type.
        
        Args:
            results: List of crawl results
            
        Returns:
            Dictionary mapping content types to lists of results
        """
        # Sort results by content type
        results = sorted(results, key=lambda r: r.metadata.get("content_type", "general"))
        
        # Group by content type
        grouped = {}
        for key, group in groupby(results, key=lambda r: r.metadata.get("content_type", "general")):
            grouped[key] = list(group)
            
        return grouped
    
    def _select_top_results(self, results: List[CrawlResult], max_results: int = 5) -> List[CrawlResult]:
        """
        Select top results based on relevance.
        
        Args:
            results: List of crawl results
            max_results: Maximum number of results to select
            
        Returns:
            List of selected results
        """
        # Sort by relevance score in descending order
        sorted_results = sorted(results, key=lambda r: r.relevance_score, reverse=True)
        
        # Take top N results
        return sorted_results[:max_results]
    
    def _create_document(self, content_type: str, results: List[CrawlResult], 
                        instructions: str) -> Document:
        """
        Create a document from results.
        
        Args:
            content_type: Type of content
            results: List of crawl results
            instructions: Original user instructions
            
        Returns:
            Document object
        """
        # Combine top results
        combined_content = "\n\n".join([
            f"Page: {r.title}\nURL: {r.url}\nContent: {r.content[:1500]}..."
            for r in results
        ])
        
        # Create prompt based on content type
        prompt = self._create_synthesis_prompt(content_type, combined_content, instructions)
        
        # Use LLM to synthesize content
        response = self.llm_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        
        synthesized_content = response.choices[0].message.content
        title = f"{content_type.title()} Information"
        
        # Create document
        return Document.create(
            type_=content_type,
            title=title,
            content=synthesized_content,
            source_urls=[r.url for r in results],
            instruction_prompt=instructions
        )
    
    def _create_synthesis_prompt(self, content_type: str, content: str, 
                                instructions: str) -> str:
        """
        Create a prompt for synthesizing content based on content type.
        
        Args:
            content_type: Type of content
            content: Combined content from crawl results
            instructions: Original user instructions
            
        Returns:
            Prompt for the LLM
        """
        base_prompt = f"""
        Based on these web pages about {content_type}:
        
        {content}
        
        Create a comprehensive and structured document that covers all important information.
        """
        
        # Add specific instructions based on content type
        if content_type == "faq":
            type_specific = """
            Format the content as questions and answers.
            Each question should be clear and concise.
            Group related questions together under appropriate headings.
            """
        elif content_type == "product":
            type_specific = """
            Organize information by features, benefits, and specifications.
            Include clear sections with descriptive headings.
            Highlight key product information that would be most relevant to users.
            """
        elif content_type == "pricing":
            type_specific = """
            Clearly structure different pricing tiers or options.
            Include information about what's included in each tier.
            Mention any discounts, promotions, or special offers.
            """
        else:
            type_specific = """
            Organize the information with clear headings and sections.
            Focus on the most important and relevant details.
            Ensure the document flows logically from general to specific information.
            """
        
        # Add user instructions and formatting guidance
        final_prompt = f"""
        {base_prompt}
        
        {type_specific}
        
        User instructions: "{instructions}"
        
        The document should be well-structured with:
        - A clear title
        - Organized sections with headings
        - Concise, informative content
        - No repetition or filler text
        """
        
        return final_prompt