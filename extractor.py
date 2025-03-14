from bs4 import BeautifulSoup
import json
from typing import Set, List, Dict, Any, Tuple, Optional
from urllib.parse import urlparse
from requests_html import HTMLSession
import numpy as np
from numpy import dot
from numpy.linalg import norm
import gensim.downloader as api
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

from .models import CrawlStrategy, CrawlResult
from .utils import normalize_url

# Load pre-trained word embeddings (only load once in practice)
word_vectors = api.load('word2vec-google-news-300')

class ContentExtractor:
    """Extracts and processes content from web pages."""
    
    def __init__(self, llm_client: Any):
        """
        Initialize the content extractor.
        
        Args:
            llm_client: Client for LLM API access
        """
        self.llm_client = llm_client
        self.session = HTMLSession()
    
    def extract_main_content(self, soup: BeautifulSoup) -> str:
        """
        Extract the main content from a page, filtering boilerplate.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            Extracted main content as text
        """
        # Remove common non-content elements
        for element in soup.select('nav, footer, header, script, style, [role=banner], [role=navigation]'):
            element.decompose()
            
        # First attempt: Look for main content containers
        main_elements = soup.select('main, article, .content, #content, [role=main]')
        if main_elements:
            return " ".join([elem.get_text(strip=True, separator=" ") for elem in main_elements])
            
        # Second attempt: Take the largest div by text content
        divs = soup.find_all('div')
        if divs:
            divs_with_text = [(div, len(div.get_text())) for div in divs]
            sorted_divs = sorted(divs_with_text, key=lambda x: x[1], reverse=True)
            
            if sorted_divs:
                return sorted_divs[0][0].get_text(strip=True, separator=" ")
        
        # Fallback: Just get all text
        return soup.get_text(strip=True, separator=" ")
    
    def detect_content_type(self, soup: BeautifulSoup, url: str) -> str:
        """
        Detect the type of content (FAQ, product, pricing, etc.).
        
        Args:
            soup: BeautifulSoup object of the page
            url: URL of the page
            
        Returns:
            Detected content type
        """
        url_lower = url.lower()
        if any(term in url_lower for term in ['faq', 'help', 'support']):
            return 'faq'
        if any(term in url_lower for term in ['price', 'plan', 'subscription']):
            return 'pricing'
        if any(term in url_lower for term in ['product', 'feature', 'service']):
            return 'product'
        if any(term in url_lower for term in ['contact', 'about']):
            return 'about'
            
        # Look for hints in page content
        text = soup.get_text().lower()
        if 'frequently asked' in text or 'faq' in text:
            return 'faq'
        if '$' in text and ('month' in text or 'year' in text):
            return 'pricing'
            
        return 'general'
    
    def _preprocess_text(self, text: str) -> list:
        """Preprocess text for better matching"""
        
        # Download necessary NLTK data (only needs to be done once)
        for resource in ['punkt_tab', 'stopwords', 'wordnet']:
            try:
                nltk.data.find(f'tokenizers/{resource}')
            except LookupError:
                nltk.download(resource)
        
        # Tokenize, remove stopwords, and lemmatize
        tokens = nltk.word_tokenize(text.lower())
        stop_words = set(stopwords.words('english'))
        lemmatizer = WordNetLemmatizer()
        
        return [lemmatizer.lemmatize(token) for token in tokens if token.isalnum() and token not in stop_words]
    
    def _calculate_semantic_similarity(self, tokens: list, keywords: list) -> float:
        """Calculate semantic similarity using word embeddings"""
        
        # Calculate document embedding (average of word vectors)
        doc_vector = self._get_document_vector(tokens, word_vectors)
        keyword_vector = self._get_document_vector(keywords, word_vectors)
        
        # Calculate cosine similarity
        
        if norm(doc_vector) * norm(keyword_vector) == 0:
            return 0.0
            
        return max(0.0, dot(doc_vector, keyword_vector) / (norm(doc_vector) * norm(keyword_vector)))
    
    def _get_document_vector(self, tokens: list, word_vectors):
        """Convert a document to a vector by averaging word vectors"""
        
        vectors = [word_vectors[word] for word in tokens if word in word_vectors]
        if not vectors:
            return np.zeros(word_vectors.vector_size)
            
        return np.mean(vectors, axis=0)
    
    def calculate_relevance(self, content: str, strategy: CrawlStrategy) -> float:
        """
        Calculate relevance score of content based on crawl strategy.
        
        Args:
            content: Page content
            strategy: Crawl strategy
            
        Returns:
            Relevance score between 0 and 1
        """
            
        # Check keyword matches
        # keyword_score = 0
        # if strategy.keywords:
        #     content_lower = content.lower()
        #     matches = sum(1 for keyword in strategy.keywords if keyword.lower() in content_lower)
        #     keyword_score = min(matches / len(strategy.keywords), 1.0) if strategy.keywords else 0
        
        # Preprocess content
        tokens = self._preprocess_text(content)
        keyword_score =self._calculate_semantic_similarity(tokens, strategy.keywords)
            
        # Use LLM for more complex relevance assessment if content is substantial
        if len(content) > 100 and strategy.task:
            try:
                prompt = f"""
                Rate the relevance of this content on a scale of 0.0 to 1.0 for the task:
                "{strategy.task}"
                
                Content:
                "{content[:1500]}..."
                
                Return only a number between 0 and 1.
                """
                
                response = self.llm_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=10
                )
                
                llm_score = float(response.choices[0].message.content.strip())
                # Combine scores (70% LLM, 30% keyword)
                return (llm_score * 0.7) + (keyword_score * 0.3)
            except:
                return keyword_score
        
        return keyword_score
    
    def extract_links(self, base_url: str, strategy: CrawlStrategy, llm_client) -> List[str]:
        """
        Extract links from the page content that match the crawl strategy.
        
        Args:
            base_url: Base URL of the page
            strategy: Crawl strategy
            llm_client: LLM client
        Returns:
            Set of extracted URLs
        """
        links = set()
        response = self.session.get(base_url)
        all_links = response.html.absolute_links
        
        for link in all_links:
            links.add(normalize_url(link))
        links = self._should_follow_link(links, strategy, llm_client)        
        return links
    
    def _should_follow_link(self, all_links: List[str], strategy: CrawlStrategy, llm_client) -> List[str]:
        """
        Determine if a link should be followed based on strategy.
        
        Args:
            all_links: set of urls from page
            strategy: Crawl strategy
            llm_client: llm client
            
        Returns:
            list of links to follow
        """
        
        keywords = ", ".join(strategy.keywords)
        content_types = ", ".join(strategy.content_types)
        prompt = f"""
            I am trying to perform this task: "{strategy.task}". 
            Keywords related to this task are {keywords}. 
            Content types related to this task are {content_types}.
            Given below are the list of website addresses which may relevant information.

            {all_links}
            
            Please think hard and make a best guess on which these links may have information relevant to my task.

            Format your response as a JSON objects with this field:
            - relevant_links: list of links relevant for the task
            """
        response = llm_client.chat.completions.create(
                model="gpt-4.5-preview-2025-02-27",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
        return json.loads(response.choices[0].message.content)['relevant_links']
    
        
