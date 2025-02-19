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

class RevenuePerspective(Enum):
    REVENUE_BY_SOURCE = "Revenue by Source"
    REVENUE_BY_GEOGRAPHY = "Revenue by Geography"

class RevenueDetailItem(BaseModel):
    business_unit_id: Optional[int] = Field(None, description="ID of the business unit the revenue item belongs to (optional for geography)")
    unit_title: str = Field(..., description="Title of the business unit of the revenue item, product/service name or country/region")
    amount: float = Field(..., description="Amount of revenue in millions of dollars")

class BusinessUnitCategory(BaseModel):
    id: int = Field(..., description="ID of the revenue category the group of business unit or service name")
    name: str = Field(..., description="Name of the revenue category the group of business unit or service name")

class RevenueTable(BaseModel):
    title: str = Field(..., description="Title of the table")
    perspective: RevenuePerspective = Field(..., description="Perspective of the table")
    items: List[RevenueDetailItem] = Field(..., description="List of revenue items in the table")
    total: float = Field(..., description="Total amount of revenue in millions of dollars")

class ExtractionResult(BaseModel):
    business_units: List[BusinessUnitCategory] = Field(..., description="List of business units. this list must not be empty")
    revenue_tables: List[RevenueTable] = Field(..., description="List of revenue tables. this list must not be empty but maximum of 2 tables. please choose wisely")

def llm_extraction(symbol: str, filepath: pathlib.Path) -> ExtractionResult:
    client = genai.Client(api_key=os.environ["RKET_GEMINI_API_KEY"])

    prompt = f"""
    <task>
    You are provided with a 10-K filing document for {symbol}. Your goal is to extract every available and detailed revenue breakdown for the latest fiscal year mentioned in the document. Organize the extracted data into a maximum of 2 revenue tables according to the following perspectives:

    1. Revenue by Source  
       - Identify and extract the full breakdown of revenue details by source. Look for all granular revenue lines and all revenue tables, such as individual product names (e.g., "Product A", "Product B", "Brand C", "Service X", etc.), services, and any subcategories provided in the filing.
       - Ensure that if there are multiple levels of detail (e.g., categories and sub-items), every distinct revenue stream is captured.

    2. Revenue by Geography  
       - Extract the full breakdown of revenue by geographic regions. Include all details such as major regions, countries or even more localized geographic segments if available.

    The extracted data should be organized into the following schema:

    - ExtractionResult
      - **business_units**: A non-empty list of BusinessUnitCategory objects. You must identify at least one business unit category. Each BusinessUnitCategory contains:
        - **id**: A unique identifier for the business unit category
        - **name**: The name of the business unit category
        - **total**: The total revenue for this business unit in millions of dollars
        Note: This list must not be empty - always identify and categorize at least one business unit from the revenue data

      - **revenue_tables**: A list of RevenueTable objects, each containing:
        - **title**: A descriptive title for the table (e.g., "2024 Revenue by Source")
        - **perspective**: One of the following values from RevenuePerspective enum:
          - REVENUE_BY_SOURCE: "Revenue by Source"
          - REVENUE_BY_GEOGRAPHY: "Revenue by Geography"
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

    <response_format>
    json object
    </response_format>

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
    # List of symbols to process
    symbols = ['RTX', 'CROX', 'BYND', 'ROKU', 'ETSY', 'FUBO', 'SDC', 'SHAK', 'GPRO', 'BOOT', 'ADI', 
              'TXN', 'ADSK', 'SHW', 'CMG', 'LULU', 'SQ', 'PYPL', 'DOCU', 'MDB', 'DDOG', 'CRWD', 'ZM', 
              'HOOD', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'TSLA', 'BRK.B', 'META', 'V', 'JPM', 'JNJ', 
              'WMT', 'PG', 'UNH', 'XOM']
    
    # Create output directory if it doesn't exist
    output_dir = pathlib.Path('outputs/revenues')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for symbol in symbols:
        try:
            rprint(f"\n[bold green]Processing symbol:[/bold green] [yellow]{symbol}[/yellow]")
            
            filepath = pathlib.Path(f'downloads/{symbol}_10-K.pdf')
            if not filepath.exists():
                rprint(f"[bold red]Error:[/bold red] PDF file not found for {symbol}")
                continue
                
            response = llm_extraction(symbol, filepath)
            
            # Save response to JSON file
            output_file = output_dir / f"{symbol}-rev.json"
            # First get the JSON string
            json_data = response.model_dump_json()
            # Then write it to file
            with open(output_file, 'w') as f:
                f.write(json_data)
            
        except Exception as e:
            rprint(f"[bold red]Error processing {symbol}:[/bold red] {str(e)}")
    
if __name__ == "__main__":
    main()

