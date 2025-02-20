# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "beautifulsoup4",
#     "edgartools",
#     "playwright",
# ]
# ///
import os
import asyncio
from edgar import *
from playwright.async_api import async_playwright
from rich.console import Console
from pipeline import Pipeline
from bs4 import BeautifulSoup

set_identity(os.getenv("EDGAR_IDENTITY"))

async def download_filing(symbol: str):
    console = Console()
    console.print(f"[bold blue]Downloading filing for {symbol}...[/bold blue]")
    
    company = Company(symbol)
    filing = company.latest("10-K")
    if not filing:
        console.print(f"[bold red]No 10-K filing found for {symbol}[/bold red]")
        return
    
    console.print("[yellow]Downloading HTML content...[/yellow]")
    html = filing.attachments[1].download()
    pdf_path = f"downloads/{symbol}_10-K.pdf"

    # Modify HTML to add revenue banners
    console.print("[yellow]Adding revenue banners to tables...[/yellow]")
    modified_html = find_table_elements(html)
    
    await create_pdf_from_html(modified_html, pdf_path)
    console.print(f"[bold green]✓[/bold green] Filing downloaded and converted for {symbol}")

def fetch_html_content(url: str) -> BeautifulSoup:
    """Fetch HTML content from URL and return BeautifulSoup object
    
    Args:
        url (str): URL to fetch content from
        
    Returns:
        BeautifulSoup: Parsed HTML content
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return BeautifulSoup(response.text, 'html.parser')


def find_us_gaap_elements(soup: BeautifulSoup) -> list:
    """Find all ix tags with us-gaap namespace in the HTML
    
    Args:
        soup (BeautifulSoup): Parsed HTML content
        
    Returns:
        list: List of elements with us-gaap namespace
    """
    return soup.find_all('ix:nonfraction', attrs={'name': lambda x: x and x.startswith('us-gaap:')})


def filter_elements_by_keywords(elements: list, keywords: list) -> list:
    """Filter elements whose names contain any of the given keywords
    
    Args:
        elements (list): List of elements to filter
        keywords (list): List of keywords to match against
        
    Returns:
        list: Filtered list of elements
    """
    return [elem for elem in elements 
            if any(keyword.lower() in elem['name'].lower() 
                  for keyword in keywords)]


def find_parent_tables(elements: list) -> list:
    """Find unique parent table elements for the given elements
    
    Args:
        elements (list): List of elements to find parent tables for
        
    Returns:
        list: List of unique parent table elements
    """
    return list({elem.find_parent('table') 
                for elem in elements 
                if elem.find_parent('table')})

def create_revenue_banner() -> str:
    """Create a banner with revenue message
    
    Returns:
        str: HTML string for the banner
    """
    return '<div style="background-color: red; color: yellow; padding: 4px; text-align: center; margin: 4px 0;">THIS IS THE TABLE YOU ARE LOOKING FOR!</div>'

def find_table_elements(html_content: str) -> str:
    """Find tables containing us-gaap elements with specific keywords using a monadic pipeline
    and return modified HTML with banners
    
    Args:
        html_content (str): HTML content to process
        
    Returns:
        str: Modified HTML content with revenue banners
    """
    # Target keywords to search for
    keywords = ["revenue"]
    
    # Create pipeline transformations with partial application
    find_elements = lambda soup: find_us_gaap_elements(soup)
    filter_by_keywords = lambda elements: filter_elements_by_keywords(elements, keywords)
    
    # Parse HTML content
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Add CSS styling to head
    head = soup.find('head')
    if not head:
        head = soup.new_tag('head')
        soup.insert(0, head)
    
    style = soup.new_tag('style')
    style.string = '''
        table { 
            border-collapse: collapse !important; 
            width: 100% !important;
        }
        td, th { 
            border: 1px solid black !important;
        }
    '''
    head.append(style)
    
    # Find revenue tables
    revenue_tables = (Pipeline(soup)
            .bind(find_elements)
            .bind(filter_by_keywords)
            .bind(find_parent_tables)
            .run())
    
    # Add banner above each revenue table and style the table
    banner_html = create_revenue_banner()
    for table in revenue_tables:
        # Add banner above the table
        
        banner = BeautifulSoup(banner_html, 'html.parser')
        table.insert_before(banner)
    
    return str(soup)

async def create_pdf_from_html(html: str, pdf_path: str):
    console = Console()
    console.print("[bold blue]Starting PDF creation process...[/bold blue]")
    
    async with async_playwright() as p:
        console.print("[yellow]Launching browser...[/yellow]")
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        console.print("[yellow]Setting HTML content...[/yellow]")
        await page.set_content(html)
        
        console.print(f"[yellow]Generating PDF at: {pdf_path}[/yellow]")
        await page.pdf(path=pdf_path, print_background=True)
        
        await browser.close()
        console.print("[bold green]✓[/bold green] PDF creation completed successfully")

async def main():
    company_symbols = [
        # Small-Cap Symbols
        "RTX",
        "CROX",
        "BYND",
        "ROKU",
        "ETSY",
        "FUBO",
        "SDC",
        "SHAK",
        "GPRO",
        "BOOT",

        # Mid-Cap Symbols
        "ADI",
        "TXN",
        "ADSK",
        "SHW",
        "CMG",
        "LULU",
        "SQ",
        "PYPL",
        "DOCU",
        "MDB",
        "DDOG",
        "CRWD",
        "ZM",
        "HOOD",
        "F"

        # Large-Cap Symbols
        "AAPL",
        "MSFT",
        "AMZN",
        "GOOGL",  # or GOOG depending on preference
        "TSLA",
        "BRK.B", # or BRK.A depending on preference
        "META",
        "V",
        "JPM",
        "JNJ",
        "WMT",
        "PG",
        "UNH",
        "XOM"
    ]

    # company_symbols = ["LULU"]

    console = Console()
    total = len(company_symbols)
    
    console.print("[bold blue]Starting download of 10-K filings[/bold blue]")
    console.print(f"[yellow]Total companies to process: {total}[/yellow]")
    
    # Create downloads directory if it doesn't exist
    os.makedirs("downloads", exist_ok=True)
    
    for idx, symbol in enumerate(company_symbols, 1):
        console.rule(f"[bold cyan]Processing {symbol} ({idx}/{total})[/bold cyan]")
        try:
            await download_filing(symbol)
        except Exception as e:
            console.print(f"[bold red]Error processing {symbol}: {str(e)}[/bold red]")
    
    console.rule("[bold green]Download Process Complete[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())

