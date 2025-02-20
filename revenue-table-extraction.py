# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "beautifulsoup4",
#     "google-genai",
#     "pydantic",
#     "rich",
# ]
# ///
import os
import pathlib

from enum import Enum
from google import genai
from google.genai import types
from typing import List, Optional
from pydantic import BaseModel, Field
from rich import print as rprint
from rich.console import Console
from rich.markdown import Markdown

class RelatedTopic(Enum):
    SOURCE = "Revenue by Source"
    GEOGRAPHY = "Revenue by Geography"
    BOTH = "Both"

class TableContent(BaseModel):
    markdown_table: str = Field(..., description="Markdown table content")
    page_number: int = Field(..., description="Page number the table exists on. it should be the number on the bottom of page")

client = genai.Client(api_key=os.environ["RKET_GEMINI_API_KEY"])

# Ask for symbol input with rich styling
rprint("[bold cyan]Enter stock symbol[/bold cyan] (e.g. META, AAPL): ", end="")
symbol = input().strip().upper()
rprint(f"[bold green]Processing for symbol:[/bold green] [yellow]{symbol}[/yellow]")

filepath = pathlib.Path(f'downloads/{symbol}_10-K.pdf')

prompt = """
<task>
Extract the table from the 10-K document. by focused on only the table that relevant to Revenue of this company.
</task>

<table-that-relevant-to-revenue-scope>
1. contain the number and name of each revenue source
2. contain the number and name of each revenue by geography
3. contain the number and name of both revenue source and revenue by geography
</table-that-relevant-to-revenue-scope>

<context>
The 10-K document
</context>

<response-format>
The response will be in JSON format, with a list of TableContent objects.
</response-format>

<concern-points>
Try to extract all columns and rows from the table. Because some table has a complex multiple columns
</concern-points>
"""
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=[
        types.Part.from_bytes(
            data=filepath.read_bytes(),
            mime_type='application/pdf',
        ),
        prompt
    ],
    config={
        'temperature': 0,
        'response_mime_type': 'application/json',
        'response_schema': list[TableContent],
    }
)

def cost_estimate(usage_metadata: types.GenerateContentResponseUsageMetadata) -> float:
    """Calculate the estimated cost based on token usage.
    
    Args:
        usage_metadata: Usage metadata from the Gemini API response
        
    Returns:
        float: Estimated cost in USD
    """
    # Constants for pricing (USD per 1M tokens)
    INPUT_PRICE = 0.10  # $0.10 per 1M tokens for text/image input
    OUTPUT_PRICE = 0.40  # $0.40 per 1M tokens for text output
    
    # Calculate costs
    input_cost = (usage_metadata.prompt_token_count / 1_000_000) * INPUT_PRICE
    output_cost = (usage_metadata.candidates_token_count / 1_000_000) * OUTPUT_PRICE
    
    return input_cost + output_cost

rprint("[bold blue]Usage Metadata:[/bold blue]")
rprint(response.usage_metadata)

# Calculate and display cost estimate
total_cost = cost_estimate(response.usage_metadata)
rprint(f"[bold yellow]Estimated Cost:[/bold yellow] ${total_cost:.6f} USD")

rprint("\n[bold green]Parsed Response:[/bold green]")
rprint(response.parsed)

