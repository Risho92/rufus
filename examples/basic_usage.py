import os
import sys
import logging
from pprint import pprint

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from rufus import RufusClient

# Example using the San Francisco government website
def main():
    """Run an example for San Francisco government website."""
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Get API key from environment
    api_key = os.getenv('RUFUS_API_KEY')
    if not api_key:
        print("Please set the RUFUS_API_KEY environment variable.")
        return
    
    # Initialize client
    client = RufusClient(api_key=api_key, max_pages=1)
    
    # Define instructions for HR chatbot
    instructions = "We're making a chatbot for the HR in San Francisco. Find information about employment, benefits, and HR policies."
    
    # Define URL to scrape
    url = "https://www.sfgov.org"
    
    print(f"Scraping {url} with instructions: {instructions}")
    print("This may take several minutes...")
    
    # Scrape website
    documents = client.scrape(url, instructions)
    
    # Print results summary
    print(f"\nFound {len(documents)} documents:")
    for i, doc in enumerate(documents):
        print(f"\n--- Document {i+1}: {doc['title']} ---")
        print(f"Type: {doc['type']}")
        print(f"Content (first 200 chars): {doc['content'][:200]}...")
        print(f"Sources: {', '.join(doc['metadata']['source_urls'])}")
    
    # Save as JSON and text
    document_path = client.save_documents(documents)
    print(f"\nDocuments saved to {document_path}")


if __name__ == "__main__":
    main()
