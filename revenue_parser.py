import os
import requests
from bs4 import BeautifulSoup
from edgar import Company, set_identity
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from openai import OpenAI

class RevenueParser:
    def __init__(self):
        self.ns = {
            'ix': 'http://www.xbrl.org/2013/inlineXBRL',
            'us-gaap': 'http://fasb.org/us-gaap/2021',
            'dei': 'http://xbrl.sec.gov/dei/2021',
        }
    
    def cleanup_table(self, table):
        """Clean up HTML table by removing unnecessary attributes.

        Args:
            table (BeautifulSoup): The table element to clean.

        Returns:
            str: Cleaned HTML table string.
        """
        # Create a copy to avoid modifying the original
        table_copy = BeautifulSoup(str(table), 'html.parser')
        
        # List of attributes to remove
        attrs_to_remove = ['style', 'contextref', 'name', 'format', 'id']
        
        # Find all elements in the table
        for element in table_copy.find_all():
            # Remove specified attributes from each element
            for attr in attrs_to_remove:
                if attr in element.attrs:
                    del element[attr]
        
        return str(table_copy)
    
    def download_filing(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'} 
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"Error downloading filing: {e}")
            return None

    def convert_html_table_to_markdown(self, html_table):
        try:
            soup = BeautifulSoup(html_table, 'html.parser')
            headers = []
            header_row = soup.find('tr')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            
            rows = []
            MIN_NON_EMPTY_CELLS = 0
            for tr in soup.find_all('tr')[1:]:
                row = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                non_empty_cells = [cell for cell in row if cell and cell.strip()]
                if len(non_empty_cells) >= MIN_NON_EMPTY_CELLS:
                    row = row[:len(headers)]
                    while len(row) < len(headers):
                        row.append("")
                    rows.append(row)
            
            if not headers and rows:
                headers = [f"Column {i+1}" for i in range(len(rows[0]))]
            
            if not headers or not rows:
                return None
            
            markdown_lines = []
            markdown_lines.append("| " + " | ".join(headers) + " |")
            markdown_lines.append("| " + " | ".join(["---" for _ in headers]) + " |")
            for row in rows:
                markdown_lines.append("| " + " | ".join(row) + " |")
            
            return "\n".join(markdown_lines)
        except Exception as e:
            print(f"Error converting table: {e}")
            return None

    def get_gaaps(self, xbrl_content):
        """Extract all unique us-gaap tags from the XBRL filing.
        
        Args:
            xbrl_content (str): The XBRL filing content
            
        Returns:
            list: A list of unique us-gaap tags found in the filing
        """
        try:
            soup = BeautifulSoup(xbrl_content, 'xml')
            gaap_tags = set()
            
            # Use CSS selector to find all elements with name attribute
            elements_with_name = soup.select('[name]')
            
            # Process elements with name attribute
            for element in elements_with_name:
                name = element.get('name', '')
                if name.startswith('us-gaap:'):
                    tag = name.replace('us-gaap:', '')
                    gaap_tags.add(tag)
            
            # Handle measure elements separately as they might contain GAAP refs in content
            for measure in soup.find_all('xbrli:measure'):
                content = measure.text.strip()
                if content.startswith('us-gaap:'):
                    tag = content.replace('us-gaap:', '')
                    gaap_tags.add(tag)
            
            return sorted(list(gaap_tags)) if gaap_tags else []
            
        except Exception as e:
            print(f"Error parsing XBRL content: {e}")
            return None

    def get_tables_by_tag(self, xbrl_content, tag_name):
        """Find tables that contain child elements with ix tag having a matching name attribute.
        
        Args:
            xbrl_content (str): The XBRL filing content
            tag_name (str): The name attribute to match in ix elements
            
        Returns:
            list: A list of tables (in markdown format) that contain matching ix elements
        """
        try:
            soup = BeautifulSoup(xbrl_content, 'xml')
            tables = set()  # Use set to avoid duplicates
            
            # Find all elements with matching name attribute using CSS selector
            matching_elements = soup.select(f'[name="{tag_name}"]')

            for element in matching_elements:
                # Check if element is ix:nonNumeric or ix:numeric
                if element.name.lower() in ['nonnumeric', 'numeric', 'nonfraction', 'fraction']:
                    # Find the closest parent table
                    parent_table = element.find_parent('table')
                    if parent_table:
                        # Clean and add the HTML table to our results
                        cleaned_table = self.cleanup_table(parent_table)
                        tables.add(cleaned_table)
            
            return list(tables)
            
        except Exception as e:
            print(f"Error finding tables by tag: {e}")
            return []

    def get_openai_client(self) -> OpenAI:
        return OpenAI(
            api_key=os.getenv("OPENROUTER_TOKEN"),
            base_url="https://openrouter.ai/api/v1"
        )

    def refine_table(self, table):
        """Refine the tables by using LLM to extract relevant information.
        
        Args:
            table (str): The table to refine
        
        Returns:
            str: The refined table in markdown format
        """

        client = self.get_openai_client()
        with open('prompts/revenue_table_extractor.txt', 'r') as f:
            prompt = f.read()

        prompt = prompt.format(table=table)

        response = client.chat.completions.create(
            model="google/gemini-2.0-flash-001",
            messages=[
                {"role": "system", "content": "You are a table extraction assistant."},
                {"role": "user", "content": prompt}
            ]
        )

        content = response.choices[0].message.content

        if "no table" in content.lower():
            return ""

        return content


    def analyze_revenue_tables(self, filing_url: str) -> list:
        """Analyze revenue tables from a filing URL.
        
        Args:
            filing_url (str): The URL of the filing to analyze
            console (Console, optional): Rich console for output. If None, creates new one.
            
        Returns:
            list: List of refined revenue tables
        """
        refined_tables = []
        
        filing_content = self.download_filing(filing_url)
        
        if filing_content:
            # Get GAAP tags
            gaap_tags = self.get_gaaps(filing_content)

            # filter only tags that contain revenue
            expected_keywords = ['revenue']
            gaap_tags = [tag for tag in gaap_tags if tag.lower().startswith(tuple(expected_keywords))]
            
            # Find tables containing revenue information
            for tag in gaap_tags:
                revenue_tables = self.get_tables_by_tag(filing_content, f'us-gaap:{tag}')

                if revenue_tables:
                    for i, table in enumerate(revenue_tables, 1):
                        refined_table = self.refine_table(table)
                        refined_tables.append(refined_table)

        # filter out empty tables
        refined_tables = [table for table in refined_tables if table]

        return refined_tables

if __name__ == '__main__':
    # Initialize Rich console for beautiful output
    console = Console()
    
    # Set up parser
    parser = RevenueParser()
    
    # Set Edgar identity from environment variable
    set_identity(os.getenv("EDGAR_IDENTITY"))
    
    # Example symbol
    symbol = "AAPL"
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(f"[cyan]Fetching 10-K filing for {symbol}...", total=None)
        
        # Get company filing using Edgar tools
        company = Company(symbol)
        filing = company.latest("10-K")
        
        if not filing:
            progress.stop()
            console.print(f"[red]No 10-K filing found for {symbol}[/red]")
            exit(1)
        
        filing_url = filing.filing_url
        progress.update(task, description=f"[green]Found 10-K filing: {filing_url}[/green]")
        
        # Analyze revenue tables
        refined_tables = parser.analyze_revenue_tables(filing_url, console)
        
        progress.update(task, description="[green]Analysis completed![/green]")
