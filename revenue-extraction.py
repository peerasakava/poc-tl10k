# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "google-genai",
#     "pydantic",
#     "rich",
# ]
# ///
import os
import pathlib
import json

from enum import Enum
from google import genai
from google.genai import types
from typing import List, Optional
from pydantic import BaseModel, Field
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.pretty import Pretty

class RevenueDimension(Enum):
    BY_SOURCE = "Revenue by Source"
    BY_GEOGRAPHY = "Revenue by Geography"

class RevenueDetailItem(BaseModel):
    unit_title: str = Field(..., description="Title of the business unit of the revenue item, product/service name or country/region")
    amount: float = Field(..., description="Amount of revenue in millions of dollars")

class BusinessUnitCategory(BaseModel):
    id: int = Field(..., description="ID of the revenue category the group of business unit or service name")
    name: str = Field(..., description="Name of the revenue category the group of business unit or service name")

class RevenueTable(BaseModel):
    title: str = Field(..., description="Title of the table")
    dimension: RevenueDimension = Field(..., description="Dimension of the revenue for this table")
    items: List[RevenueDetailItem] = Field(..., description="List of revenue items in the table")
    total: float = Field(..., description="Total amount of revenue in millions of dollars")
    
    @property
    def total_from_items(self) -> float:
        return sum(item.amount for item in self.items)

class ExtractionResult(BaseModel):
    revenue_tables: List[RevenueTable] = Field(..., description="List of revenue tables. this list must not be empty but maximum of 2 tables. please choose wisely")


def llm_think_and_explain_revenue(symbol: str, filepath: pathlib.Path) -> str:
    client = genai.Client(api_key=os.environ["RKET_GEMINI_API_KEY"])

    prompt = f"""
    <task>
    You are provided with a 10-K filing document for {symbol}. Your goal is to understand the product and services of the company and summarize the company's "Revenue Stream"

    You need to explain the title/category of the revenue and number in your summarize

    FOCUS ONLY ON "SALES AND OTHER OPERATING REVENUE" IN LATEST YEAR
    </task>

    <context>
    the reader need the descriptive information to understand the company's business for investment purpose
    </context>

    <instructions>
    1. understand the business segment of the company
    2. find and analyze the table that have a banner "REVENUE RELEVANT TABLE", is it relevant to revenue or not? is it usable as a data source? [table by table]
    3. conclude the consolidated total revenue of the company from data source
    4. summarize the detail of revenue stream by each segment, product/service with consolidated number
        4.1 do it without any calculation
        4.2 [important ⚠️] this part must be relevant to product/service, brand and others that gather revenue
        4.3 just explain the number exactly from source
            4.3.1 breakdown the level of segment, product/service and brand like what are the subtotal or what are the detail
    5. summarize the detail of revenue stream by geography, country/region with consolidated number
        5.1 do it without any calculation
        5.2 just explain the number exactly from source
        5.3 [important ⚠️] the data source must be related to overall revenue not just in some product/service or segment
        5.4 if not found, skip to the next step
    6. create the markdwon table of revenue by source and revenue by geography based on the above summary
        6.1 [important ⚠️] subtotal of the revenue by source and revenue by geography should not be included
        6.2 split the revenue by source and revenue by geography according to the table
        6.3 [important ⚠️] the title of row in the table must add "(subtotal)" or "(total)" if it applies
        6.4 last row of the table must be the total of revenue
            6.4.1 [important ⚠️] if the total of table is not match the total revenue of latest year, that means the data source is not related to overall revenue, skip it.
        6.5 bottom of each table must be add the flag "usable" or "not usable" to indicate if the table is relevant to revenue
    </instructions>

    <note>
    - Explain all the potential revenue table 
    - Do not skip any significant number
    - DO NOT calculate any number. Just explain the number.
    </note>
    """

    contents = [
        types.Part.from_bytes(
            data=filepath.read_bytes(),
            mime_type='application/pdf',
        ),
        prompt
    ]
    
    generation_config = {
        "temperature": 0,
        "top_p": 0.95,
        "response_mime_type": "text/plain",
    }

    response = client.models.generate_content(
        # model="gemini-2.0-flash-001",
        model="gemini-2.0-flash-thinking-exp-01-21",
        contents=contents,
        config=generation_config
    )
    
    return response.text

def llm_extraction_from_summarized(symbol: str, summarized: str) -> ExtractionResult:
    client = genai.Client(api_key=os.environ["RKET_GEMINI_API_KEY"])

    prompt = f"""
    <task>
    You are a specialized financial data extraction expert focusing on 10-K filings. Your task is to analyze the provided summarized 10-K filing for {symbol} and extract comprehensive revenue breakdowns for the most recent fiscal year. Structure the data into 2 distinct revenue dimensions:

    1. Revenue by Source (Business Activities)
    Key Requirements:
    - Extract the most granular level of revenue sources possible
    - Include specific product names, services, brands, or business lines
    - Exclude:
        * Parent/umbrella categories when child items are available
        * Financial segment breakdowns (these belong in segment reporting)
        * Terms like "Revenue(s)" or "Net" in item names
        * Non-revenue items like operating income or profit
        * Subtotal rows
    - Standardize item names:
        * Remove redundant prefixes/suffixes
        * Maintain specific branding/product names as stated
        * Keep industry-specific terminology intact

    2. Revenue by Geography
    Key Requirements:
    - Extract geographic revenue allocations at the highest level of aggregation presented
    - Exclude:
        * Parent/umbrella categories when child items are available
        * Subtotal rows
    - For each geographic category, use either:
        * The highest-level regional grouping (e.g., "Non-U.S.", "Europe", "Asia")
        OR
        * Individual country breakdowns if no higher-level grouping exists
    - Do not include both a parent category AND its constituent countries/regions
    - Maintain the company's original primary geographic classifications
    - Standardize region names while preserving specific country mentions

    Example of correct extraction:
    If filing shows:
    - United States: $1000M
    - Non-U.S.: $2000M
        - Canada: $500M
        - UK: $800M
        - Other: $700M

    Should extract ONLY:
    - United States: $1000M
    - Non-U.S.: $2000M

    NOT:
    - United States: $1000M
    - Non-U.S.: $2000M
    - Canada: $500M
    - UK: $800M

    Validation Rules:
    1. Total revenue must be the rule of thumb to validate the extraction
    - Total revenue must equal the reported total
    - All Items summation must equal the reported total
    - Segment must not be a region or country

    2. All amounts must:
    - Be converted to millions USD if presented differently
    - Match the total revenue across both dimensions
    - Be rounded to 2 decimal places
    - Be consolidated revenue

    3. Item names must be:
    - Unique within each dimension
    - Free of redundant qualifiers
    - Consistent with original filing terminology

    4. Completeness checks:
    - Sum of items must equal the reported total
    - Both dimensions must be attempted
    - Missing data must be noted in metadata

    Error Handling:
    - Mark confidence as LOW if significant data gaps exist
    - Include "Unallocated" or "Other" categories only if explicitly stated in filing
    - Flag any currency conversion assumptions in metadata
    </task>

    <summarized-text>
    {summarized}
    </summarized-text>
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[prompt],
        config={
            'temperature': 0,
            'response_mime_type': 'application/json',
            'response_schema': ExtractionResult,
        }
    )

    return response.parsed

def llm_extraction(symbol: str, filepath: pathlib.Path) -> ExtractionResult:
    client = genai.Client(api_key=os.environ["RKET_GEMINI_API_KEY"])

    prompt = f"""
    <task>
    You are provided with a 10-K filing document for {symbol}. Your goal is to extract every available and detailed revenue breakdown for the latest fiscal year mentioned in the document. Organize the extracted data into a maximum of 2 revenue tables according to the following dimensions:

    1. Revenue by Source  
        - Identify and extract the full breakdown of revenue details by source. Look for all granular revenue lines and all revenue tables, such as individual product names (e.g., "Product A", "Product B", "Brand C", "Service X", etc.), services, and any subcategories provided in the filing.
        - Ensure that if there are multiple levels of detail (e.g., categories and sub-items), every distinct revenue stream is captured.

    2. Revenue by Geography  
        - If the document presents both high-level categories (e.g., "U.S." and "Non-U.S.") and detailed country breakdowns, only include the highest level categories in your extraction.
        - Do not mix different levels of geographic breakdowns in the same table. For example, if "Non-U.S." is provided as a total, do not include individual non-U.S. countries in the same table.

    Example of correct geographic revenue extraction:
    If the document shows:
      - United States: $246,802
      - Non-U.S.: $357,914
        - Germany: $42,159
        - Japan: $36,827
        - Australia: $22,901
        - Italy: $18,574

    The extraction should only include:
      - United States: $246,802
      - Non-U.S.: $357,914

    The extracted data should be organized into the following schema:

    - ExtractionResult
      - **business_units**: A non-empty list of BusinessUnitCategory objects. You must identify at least one business unit category. Each BusinessUnitCategory contains:
        - **id**: A unique identifier for the business unit category
        - **name**: The name of the business unit category
        - **total**: The total revenue for this business unit in millions of dollars
        Note: This list must not be empty - always identify and categorize at least one business unit from the revenue data

      - **revenue_tables**: A list of RevenueTable objects, each containing:
        - **title**: A descriptive title for the table (e.g., "2024 Revenue by Source")
        - **dimension**: One of the following values from RevenueDimension enum:
          - BY_SOURCE: "Revenue by Source"
          - BY_GEOGRAPHY: "Revenue by Geography"
        - **items**: A list of RevenueDetailItem objects, each containing:
          - **business_unit_id**: ID linking to the corresponding BusinessUnitCategory
          - **unit_title**: The specific revenue item title (product/service name or country/region)
          - **amount**: The revenue amount in millions of dollars
        - **total**: The overall total revenue for the table in millions of dollars

    **Important:** 
    - Ensure no available details are omitted
    - If the 10-K contains more granular breakdowns, include all such details accordingly
    - Focus solely on the latest fiscal year's data
    - All revenue amounts should be in millions of dollars
    </task>

    <important>
    - Return only the table that have total match to the total revenue of the summarized text
    </important>

    <response_format>
    json object
    </response_format>

    <guidelines>
    - Pay special attention to the page that contains banner "Check This Table!". It will help you to find the table easily because we added a banner above table that have potential to be revenue table.
    </guidelines>

    <note>
    Your extraction should include every available detail from the 10-K, breaking down revenue into as many specific categories and items as provided. Do not limit the number of categories or items—even if the summary sections group items broadly, refer to detailed breakdowns or supplemental figures if they exist.
    </note>
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
            'top_p': 1,
            'response_mime_type': 'application/json',
            'response_schema': ExtractionResult,
        }
    )
    
    return response.parsed

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

def main():
    console = Console()
    
    # Create output directory if it doesn't exist
    output_dir = pathlib.Path('outputs/revenues')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    symbol = None
    while True:
        # Clear screen for better UX
        console.clear()
        console.print("[bold cyan]Revenue Extraction Tool[/bold cyan]", justify="center")
        console.print("[dim]Press Ctrl+C to exit[/dim]", justify="center")
        console.print("")
        
        # Get symbol input from user if not repeating
        if symbol is None:
            symbol = console.input("[bold blue]Enter stock symbol (e.g. AAPL): [/bold blue]").strip().upper()
            
            if not symbol:
                console.print("[bold red]Error:[/bold red] Symbol cannot be empty")
                console.input("[dim]Press Enter to continue...[/dim]")
                continue
            
        try:
            rprint(f"\n[bold green]Processing symbol:[/bold green] [yellow]{symbol}[/yellow]")
            
            filepath = pathlib.Path(f'downloads/{symbol}_10-K.pdf')
            if not filepath.exists():
                rprint(f"[bold red]Error:[/bold red] PDF file not found for {symbol}")
                console.input("[dim]Press Enter to continue...[/dim]")
                continue
                
            summarized_text = llm_think_and_explain_revenue(symbol, filepath)

            console.print(Panel.fit(
                summarized_text,
                title="[bold blue]Revenue Analysis Summary[/bold blue]",
                border_style="blue",
                padding=(1, 2)
            ))

            response = llm_extraction_from_summarized(symbol, summarized_text)
            
            # Print response in a beautiful format using rich JSON formatting
            console.print(Panel.fit(
                Pretty(response.model_dump()),
                title="[bold green]Extracted Revenue Data[/bold green]",
                border_style="green",
                padding=(1, 2)
            ))
            
            # Save response to JSON file
            output_file = output_dir / f"{symbol}-rev.json"
            json_data = response.model_dump_json()
            with open(output_file, 'w') as f:
                f.write(json_data)
            
            console.print(f"\n[bold green]✓[/bold green] Data saved to: [blue]{output_file}[/blue]")
            choice = console.input("\n[dim]Press [bold]\"Enter\"[/bold] for new stock or [bold]\"r\"[/bold] to repeat the same company: [/dim]").strip().lower()
            if choice == 'r':
                continue
            symbol = None
            
        except Exception as e:
            console.print(f"[bold red]Error processing {symbol}:[/bold red] {str(e)}")
            console.input("[dim]Press Enter to continue...[/dim]")
    
if __name__ == "__main__":
    main()
