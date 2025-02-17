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

from enum import Enum
from typing import List
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from rich import print as rprint

class RevenuePerspective(Enum):
    REVENUE_BY_SOURCE = "Revenue by Source"
    REVENUE_BY_GEOGRAPHY = "Revenue by Geography"

class RevenueItem(BaseModel):
    title: str = Field(..., description="Title of the revenue item, product/service name or country/region")
    amount: float = Field(..., description="Amount of revenue in millions of dollars")

class RevenueCategory(BaseModel):
    name: str = Field(..., description="Name of the revenue category")
    items: List[RevenueItem] = Field(..., description="List of revenue items in the category")
    total: float = Field(..., description="Total amount of revenue in millions of dollars")

class RevenueTable(BaseModel):
    title: str = Field(..., description="Title of the table")
    perspective: RevenuePerspective = Field(..., description="Perspective of the table")
    categories: List[RevenueCategory] = Field(..., description="List of revenue categories")
    total: float = Field(..., description="Total amount of revenue in millions of dollars")

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

symbol = "META"
filepath = pathlib.Path(f'downloads/{symbol}_10-K.pdf')

prompt = f"""
<task>
You are provided with a 10-K filing document for {symbol}. Your goal is to extract every available and detailed revenue breakdown for the latest fiscal year mentioned in the document. Organize the extracted data into a maximum of 2 revenue tables according to the following perspectives:

1. Revenue by Source  
   - Identify and extract the full breakdown of revenue details by source. Look for all granular revenue lines and all revenue tables, such as individual product names (e.g., "Product A", "Product B", etc.), services, and any subcategories provided in the filing.
   - Ensure that if there are multiple levels of detail (e.g., categories and sub-items), every distinct revenue stream is captured.

2. Revenue by Geography  
   - Extract the full breakdown of revenue by geographic regions. Include all details such as major regions, countries or even more localized geographic segments if available.

For each revenue table, use the following schema:

- RevenueTable  
  - **title**: A descriptive title for the table (e.g., "2024 Revenue by Source").  
  - **perspective**: Use "Revenue by Source" for the first table and "Revenue by Geography" for the second.  
  - **categories**: A list of revenue categories (RevenueCategory). There is no limit on the number of categories—include all detailed categories found.
    - For each category:
      - **name**: The name of the revenue category.
      - **items**: A list of revenue items (RevenueItem) with no limit on the number of items. Each revenue item must include:
          - **title**: The specific revenue item title (e.g., a particular product or service, or a specific country/region).
          - **amount**: The revenue amount in millions of dollars.
      - **total**: The total revenue for that category in millions of dollars.
  - **total**: The overall total revenue for the table in millions of dollars.

**Important:** Ensure no available details are omitted. If the 10-K contains more granular breakdowns than just two broad items per perspective, include all such details accordingly. Focus solely on the latest fiscal year’s data.
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
        'response_mime_type': 'application/json',
        'response_schema': list[RevenueTable],
    }
)

rprint("[bold blue]Usage Metadata:[/bold blue]")
rprint(response.usage_metadata)
rprint("\n[bold green]Parsed Response:[/bold green]")
rprint(response.parsed)
