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
    console = Console()
    symbol = input("Enter company symbol: ")
    await download_filing(symbol)

if __name__ == "__main__":
    asyncio.run(main())

