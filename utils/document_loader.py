# utils/document_loader.py
# This file reads PDFs and websites and prepares them for our app

import os
import json
import requests
import pdfplumber
from bs4 import BeautifulSoup
from langchain.schema import Document

# ─────────────────────────────────────────────
# PART 1: READ A SINGLE PDF FILE
# ─────────────────────────────────────────────

def load_pdf(file_path, country, doc_type):
    """
    Opens a PDF file and reads all the text from it
    
    Think of this like:
    A person opening a book and typing out every word
    
    file_path = where the PDF is stored
    country   = india/uae/saudi_arabia/uk
    doc_type  = aml/banking/insurance/others
    """
    documents = []
    
    try:
        with pdfplumber.open(file_path) as pdf:
            
            # Go through every page of the PDF
            for page_num, page in enumerate(pdf.pages):
                
                # Extract text from this page
                text = page.extract_text()
                
                # Skip if page has no text
                if not text or text.strip() == "":
                    continue
                
                # Clean up the text a little
                text = text.strip()
                
                # Create a document with labels (metadata)
                # Think of metadata like a sticky note on the page
                # telling us where this page came from
                doc = Document(
                    page_content=text,
                    metadata={
                        "source": os.path.basename(file_path),
                        "country": country,
                        "type": doc_type,
                        "page": page_num + 1,
                        "source_type": "pdf"
                    }
                )
                documents.append(doc)
        
        print(f"✅ Loaded PDF: {os.path.basename(file_path)} "
              f"({len(documents)} pages)")
        
    except Exception as e:
        print(f"❌ Error loading PDF {file_path}: {str(e)}")
    
    return documents


# ─────────────────────────────────────────────
# PART 2: READ ALL PDFS FROM A FOLDER
# ─────────────────────────────────────────────

def load_pdfs_from_folder(country, doc_type):
    """
    Goes into a folder and reads ALL PDFs inside it
    
    Think of this like:
    A person going to a shelf and reading 
    every single book on that shelf
    
    country  = india/uae/saudi_arabia/uk
    doc_type = aml/banking/insurance/others
    """
    all_documents = []
    
    # Build the folder path
    # Example: data/documents/india/aml/
    folder_path = os.path.join(
        "data", "documents", country, doc_type
    )
    
    # Check if folder exists
    if not os.path.exists(folder_path):
        print(f"⚠️  Folder not found: {folder_path}")
        return []
    
    # Get list of all PDF files in the folder
    pdf_files = [
        f for f in os.listdir(folder_path) 
        if f.lower().endswith('.pdf')
    ]
    
    # If no PDFs found
    if not pdf_files:
        print(f"⚠️  No PDFs found in: {folder_path}")
        return []
    
    # Read each PDF one by one
    for pdf_file in pdf_files:
        file_path = os.path.join(folder_path, pdf_file)
        docs = load_pdf(file_path, country, doc_type)
        all_documents.extend(docs)
    
    print(f"📚 Total pages loaded from {country}/{doc_type}: "
          f"{len(all_documents)}")
    
    return all_documents


# ─────────────────────────────────────────────
# PART 3: READ A SINGLE WEBSITE LINK
# ─────────────────────────────────────────────

def load_url(url_info, country, doc_type):
    """
    Opens a website and reads all the text from it
    
    Think of this like:
    A person opening a webpage and copying all the text
    
    url_info = dictionary with name, url, description
    country  = india/uae/saudi_arabia/uk
    doc_type = aml/banking/insurance/others
    """
    documents = []
    
    try:
        # Set up browser-like headers
        # Some websites block robots, this helps us look like a browser
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        
        # Open the website (timeout=30 means wait max 30 seconds)
        response = requests.get(
            url_info["url"], 
            headers=headers, 
            timeout=30
        )
        
        # Check if website opened successfully
        response.raise_for_status()
        
        # Parse the website content
        # BeautifulSoup is like a tool that 
        # extracts only the readable text
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove navigation menus, footers etc
        # We only want the main content
        for tag in soup(["script", "style", "nav", 
                         "footer", "header"]):
            tag.decompose()
        
        # Get the clean text
        text = soup.get_text(separator='\n')
        
        # Clean up extra blank lines
        lines = [
            line.strip() 
            for line in text.splitlines() 
            if line.strip()
        ]
        text = '\n'.join(lines)
        
        # Skip if no text found
        if not text:
            print(f"⚠️  No text found at: {url_info['url']}")
            return []
        
        # Create document with labels
        doc = Document(
            page_content=text,
            metadata={
                "source": url_info.get("name", url_info["url"]),
                "url": url_info["url"],
                "country": country,
                "type": doc_type,
                "source_type": "url",
                "description": url_info.get("description", "")
            }
        )
        documents.append(doc)
        
        print(f"✅ Loaded URL: {url_info.get('name', url_info['url'])}")
        
    except Exception as e:
        print(f"❌ Error loading URL {url_info.get('url', '')}: "
              f"{str(e)}")
    
    return documents


# ─────────────────────────────────────────────
# PART 4: READ ALL LINKS FROM links.json
# ─────────────────────────────────────────────

def load_urls_from_config(country, doc_type):
    """
    Opens links.json and loads all websites 
    for a specific country and type
    
    Think of this like:
    A person reading a list of websites
    and visiting each one to read the content
    """
    documents = []
    
    try:
        # Open the links.json file
        with open("links.json", "r") as f:
            links_config = json.load(f)
        
        # Get links for this specific country and type
        # Example: links for india → aml
        country_links = links_config.get(country, {})
        type_links = country_links.get(doc_type, [])
        
        # If no links configured
        if not type_links:
            print(f"⚠️  No links configured for "
                  f"{country}/{doc_type}")
            return []
        
        # Visit each link and read it
        for url_info in type_links:
            docs = load_url(url_info, country, doc_type)
            documents.extend(docs)
        
    except FileNotFoundError:
        print("⚠️  links.json not found")
    except Exception as e:
        print(f"❌ Error loading links config: {str(e)}")
    
    return documents


# ─────────────────────────────────────────────
# PART 5: LOAD EVERYTHING FOR A COUNTRY+TYPE
# ─────────────────────────────────────────────

def load_all_documents(country, doc_type):
    """
    This is the MAIN function that loads everything
    Both PDFs and Links for a country + type
    
    Think of this like:
    The head librarian who calls everyone:
    "Hey PDF reader, read all PDFs!"
    "Hey web reader, read all websites!"
    Then combines everything together
    """
    all_documents = []
    
    print(f"\n📂 Loading documents for: "
          f"{country.upper()} → {doc_type.upper()}")
    print("─" * 50)
    
    # Load PDFs
    pdf_docs = load_pdfs_from_folder(country, doc_type)
    all_documents.extend(pdf_docs)
    
    # Load URLs
    url_docs = load_urls_from_config(country, doc_type)
    all_documents.extend(url_docs)
    
    print(f"📊 Total documents loaded: {len(all_documents)}")
    print("─" * 50)
    
    return all_documents


# ─────────────────────────────────────────────
# PART 6: LOAD ALL DOCUMENTS FOR A COUNTRY
# (Used when first search finds nothing)
# ─────────────────────────────────────────────

def load_all_country_documents(country):
    """
    Loads ALL documents for an entire country
    This is used in Step 2 of our search logic:
    
    If India+AML has no answer →
    Load ALL India documents and search again
    """
    all_documents = []
    
    # All possible types
    all_types = ["aml", "banking", "insurance", "others"]
    
    print(f"\n🌍 Loading ALL documents for: {country.upper()}")
    print("─" * 50)
    
    for doc_type in all_types:
        docs = load_all_documents(country, doc_type)
        all_documents.extend(docs)
    
    print(f"📊 Total country documents loaded: "
          f"{len(all_documents)}")
    
    return all_documents
