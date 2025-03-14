import requests
from bs4 import BeautifulSoup
from typing import Set, List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import time
import logging
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run without GUI
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.265 Safari/537.36"
)

from .models import CrawlResult, CrawlStrategy
from .extractor import ContentExtractor
from .utils import setup_logger, normalize_url


class WebCrawler:
    """Crawls websites based on user instructions."""
    
    def __init__(self, llm_client: Any, max_pages: int, concurrency: int, max_depth: int, min_relevance: float):
        """
        Initialize the web crawler.
        
        Args:
            llm_client: Client for LLM API access
            max_pages: Maximum number of pages to crawl
            concurrency: Number of concurrent requests
        """
        self.llm_client = llm_client
        self.max_pages = max_pages
        self.concurrency = concurrency
        self.max_depth = max_depth
        self.min_relevance = min_relevance
        self.extractor = ContentExtractor(llm_client)
        self.visited_urls = set()
        self.headers = {
            'User-Agent': 'Rufus/1.0 - Web Data Extraction Tool for RAG Systems'
        }
        self.logger = setup_logger("Rufus.WebCrawler")
        # self.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
    
    def create_crawl_strategy(self, start_url: str, instructions: str) -> CrawlStrategy:
        """
        Use LLM to create a crawling strategy based on user instructions.
        
        Args:
            start_url: Starting URL for crawling
            instructions: User instructions
            
        Returns:
            CrawlStrategy object
        """
        if not instructions:
            return CrawlStrategy()
        
        prompt = f"""
        I need to extract information from {start_url} based on these instructions:
        "{instructions}"
        
        Please create a crawling strategy with:
        1. Important keywords to look for
        2. Types of pages that would be most relevant (e.g., FAQ, pricing, product info)
        3. What specific information to extract
        
        Format your response as a JSON object with these fields:
        - keywords: [list of important keywords]
        - content_types: [list of relevant content types]
        - task: "description of the task"
        """
        
        try:
            response = self.llm_client.chat.completions.create(
                model="gpt-4.5-preview-2025-02-27",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            strategy_dict = json.loads(response.choices[0].message.content)
            self.logger.info(f"Created crawl strategy: {strategy_dict}")
            return CrawlStrategy.from_dict(strategy_dict)
            
        except Exception as e:
            self.logger.error(f"Failed to create strategy: {str(e)}")
            return CrawlStrategy(task=instructions)
    
    def crawl(self, start_url: str, strategy: CrawlStrategy) -> List[CrawlResult]:
        """
        Crawl a website based on the provided strategy.
        
        Args:
            start_url: Starting URL for crawling
            strategy: Crawl strategy
            
        Returns:
            List of CrawlResult objects
        """
        self.logger.info(f"Starting crawl of {start_url}")
        
        # Reset state for new crawl
        self.visited_urls = set()
        queue = [(start_url, 0)]  # (url, depth)
        results = []
        
        # Main crawling loop
        while queue and len(self.visited_urls) < self.max_pages:
            # Process batch of URLs concurrently
            batch_size = min(self.concurrency, len(queue))
            batch = [queue.pop(0) for _ in range(batch_size)]
            
            with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
                crawl_results = list(executor.map(
                    lambda x: self._process_url(x[0], x[1], strategy), 
                    batch
                ))
            
            for result in crawl_results:
                if result.content:                              
                    results.append(result)
                
                # Only process links if we're within depth limit
                current_depth = result.metadata.get("depth", 0)
                if current_depth < self.max_depth:
                    
                    # Extract new URLs from the page
                    new_urls = self.extractor.extract_links(result.url, strategy, self.llm_client)
                    
                    # Add new URLs to queue
                    for url in new_urls:
                        if url not in self.visited_urls and len(self.visited_urls) < self.max_pages:
                            queue.append((url, current_depth + 1))
        
        self.logger.info(f"Crawl complete. Visited {len(self.visited_urls)} pages, found {len(results)} relevant pages")
        return results
    
    def _process_url(self, url: str, depth: int, strategy: CrawlStrategy) -> Optional[CrawlResult]:
        """
        Process a single URL by downloading and analyzing content.
        
        Args:
            url: URL to process
            depth: Current crawl depth
            strategy: Crawl strategy
            
        Returns:
            CrawlResult object if successful, None otherwise
        """
        normalized_url = normalize_url(url)
        if normalized_url in self.visited_urls:
            return None
            
        self.visited_urls.add(normalized_url)
        self.logger.info(f"Processing URL: {url} (depth: {depth})")
        
        try:
            content = None
            title = None
            relevance_score = 0
            # Add a small delay to be polite
            # time.sleep(0.5)
            
            # Download the page
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
            # driver.get(url)
            # time.sleep(20)
            # # WebDriverWait(driver, 30)
            # response = driver.page_source
            
            # # Parse content
            # soup = BeautifulSoup(response, 'html.parser')
            
            # Extract main content (filtering out nav, ads, etc.)
            main_content = self.extractor.extract_main_content(soup)
            
            # Determine relevance score
            relevance_score = self.extractor.calculate_relevance(main_content, strategy)
            
            # Extract title
            title = soup.title.text.strip() if soup.title else url
            
            # Only return results above relevance threshold
            if relevance_score > self.min_relevance:
                content = main_content
            # driver.quit()
            return CrawlResult(
                url=url,
                content=content,
                title=title,
                relevance_score=relevance_score,
                metadata={
                    "depth": depth, 
                    "content_type": self.extractor.detect_content_type(soup, url),
                    "html": response.text  # Store the original HTML for potential future use
                }
            )
            # return None
            
        except Exception as e:
            self.logger.error(f"Error processing {url}: {str(e)}")
            # driver.quit()
            return CrawlResult(
                url=url,
                content=content,
                title=title,
                relevance_score=relevance_score,
                metadata={
                    "depth": depth, 
                    "content_type": None,
                    "html": None  # Store the original HTML for potential future use
                }
            )