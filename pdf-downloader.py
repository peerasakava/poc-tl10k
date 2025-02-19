# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "edgartools",
#     "playwright",
# ]
# ///
import os
import asyncio
from edgar import *
from playwright.async_api import async_playwright
from rich.console import Console

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
    
    await create_pdf_from_html(html, pdf_path)
    console.print(f"[bold green]✓[/bold green] Filing downloaded and converted for {symbol}")

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
        await page.pdf(path=pdf_path)
        
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

