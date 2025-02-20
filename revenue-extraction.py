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

class RevenuePerspective(Enum):
    REVENUE_BY_SOURCE = "Revenue by Source"
    REVENUE_BY_GEOGRAPHY = "Revenue by Geography"

class RevenueDetailItem(BaseModel):
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

    FOCUS ONLY ON "SALES AND OTHER OPERATING REVENUE"
    </task>

    <context>
    the reader need the descriptive information to understand the company's business for investment purpose
    </context>

    <instructions>
    1. UNDERSTAND THE BUSINESS SEGMENT OF THE COMPANY
    2. FIND THE TOTAL REVENUE OF THE COMPANY
    3. FIND THE DETAIL OF REVENUE STREAM BY EACH SEGMENT, PRODUCT/SERVICE AND COUNTRY/REGION
    </instructions>

    <note>
    - Pay special attention to the page that contains banner "THIS IS THE TABLE YOU ARE LOOKING FOR!". It will help you to find the table easily because we added a banner above table that have potential to be revenue table.
    - Explain all the potential revenue table 
    - Do not skip any significant number
    - DO NOT calculate any number. Just explain the number.
    </note>
    """

    # prompt = f"""
    # Revenue Analysis from 10-K Filing for {symbol}

    # **Objective:**  
    # Extract and summarize detailed information on the company's revenue streams from its 10-K filing. The summary is for investment insights and focuses solely on revenue figures without interpreting or calculating them.

    # **Task Description:**  
    # You are provided with the 10-K filing document for the company identified by {symbol}. Your goal is to analyze the document, understand the company's business segments, and compile a detailed summary of its revenue sources. Specifically, you must:

    # 1. **Business Overview:**  
    # - Identify and describe the business segments that contribute to the company's revenue.
    # - Focus on understanding the context of the company's products and services.

    # 2. **Revenue Identification:**  
    # - Locate the total revenue figure of the company.
    # - **IMPORTANT:** Only consider "REVENUE". **Do not include** any figures related to "OTHER INCOME", "NET ASSETS", "NET LOSSES", or "INTERSEGMENT REVENUE".

    # 3. **Revenue Stream Breakdown:**  
    # - Detail the revenue streams segmented by:
    #     - Business segment
    #     - Product or service category
    #     - Country or geographic region
    # - Clearly label and explain each revenue category along with its corresponding numerical value as stated in the document.

    # 4. **Utilize Key Document Markers:**  
    # - Pay special attention to any table that is preceded by the banner:  
    #     **"THIS IS THE TABLE YOU ARE LOOKING FOR!"**  
    #     This banner indicates a critical table likely containing the revenue figures you need.

    # 5. **Reporting Requirements:**  
    # - Explain every potential revenue table found.
    # - Ensure that every significant number is included and accurately reported.
    # - **Do not perform any mathematical calculations.** Your role is to extract and explain the numbers as presented in the document.

    # **Context for Use:**  
    # The information you compile will serve as a key resource for investors. It provides an in-depth understanding of the company’s revenue streams, which is critical for assessing business performance and making informed investment decisions.

    # **Additional Notes:**  
    # - Maintain focus on revenue-related data and disregard any unrelated financial numbers.
    # - The summary must be comprehensive and free from ambiguity so that investors can confidently interpret the company’s business model.
    # """
   
    contents = [
        types.Part.from_bytes(
            data=filepath.read_bytes(),
            mime_type='application/pdf',
        ),
        prompt
    ]
    
    response = client.models.generate_content(
        model="gemini-2.0-flash-001",
        contents=contents,
        config={
            'temperature': 0,
            'top_p': 1
        }
    )
    
    return response.text

def llm_extraction_from_summarized(symbol: str, summarized: str) -> ExtractionResult:
    client = genai.Client(api_key=os.environ["RKET_GEMINI_API_KEY"])

    # prompt = f"""
    # <task>
    # You are provided with a summarized 10-K filing document for {symbol}. Your goal is to extract every available and detailed revenue breakdown for the latest fiscal year mentioned in the document. Organize the extracted data into just 2 revenue tables according to the following categories:

    # 1. Revenue by Source  
    #    - Identify and extract the fully detailed breakdown of revenue by source. Include all details such as individual product names (e.g., "Product A", "Product B", "Brand C", "Service X", etc.), services, this must be atomized but not seperate financial activities in the segment.
    #    - Not contain the up-level category to the item.
    #    - Not contain the word "Revenue" or "Revenues" or "Net" in the item title.

    # 2. Revenue by Geography  
    #    - Extract the full breakdown of revenue by geographic regions. Include all details such as major regions, countries or even more localized geographic segments if available.

    # The extracted data should be organized into the following schema:

    # - ExtractionResult
    #   - **revenue_tables**: A list of RevenueTable objects, each containing:
    #     - **title**: A descriptive title for the table (e.g., "Revenue by Source")
    #     - **perspective**: One of the following values from RevenuePerspective enum:
    #       - REVENUE_BY_SOURCE: "Revenue by Source"
    #       - REVENUE_BY_GEOGRAPHY: "Revenue by Geography"
    #     - **items**: A list of RevenueDetailItem objects, each containing:
    #       - **unit_title**: The specific revenue item title (product/service name or country/region)
    #       - **amount**: The revenue amount in millions of dollars
    #     - **total**: The overall total revenue for the table in millions of dollars

    # **Important:** 
    # - Ensure no available details are omitted
    # - If the summarized text contains more granular breakdowns, include all such details accordingly
    # - Focus solely on the latest fiscal year's data
    # - All revenue amounts should be in millions of dollars
    # </task>

    # <response_format>
    # json object
    # </response_format>

    # <note>
    # Your extraction should include every available detail from the summarized text, breaking down revenue into as many specific categories and items as provided. Do not limit the number of categories or items—even if the summary sections group items broadly, refer to detailed breakdowns or supplemental figures if they exist.
    # </note>

    # <summarized-text>
    # {summarized}
    # </summarized-text>
    # """

    prompt = f"""
    <task>
    You are a specialized financial data extraction expert focusing on 10-K filings. Your task is to analyze the provided summarized 10-K filing for {symbol} and extract comprehensive revenue breakdowns for the most recent fiscal year. Structure the data into 2 distinct revenue perspectives:

    1. Revenue by Source (Business Activities)
    Key Requirements:
    - Extract the most granular level of revenue sources possible
    - Include specific product names, services, brands, or business lines
    - Exclude:
        * Parent/umbrella categories when child items are available
        * Financial segment breakdowns (these belong in segment reporting)
        * Terms like "Revenue(s)" or "Net" in item names
        * Non-revenue items like operating income or profit
    - Standardize item names:
        * Remove redundant prefixes/suffixes
        * Maintain specific branding/product names as stated
        * Keep industry-specific terminology intact

    2. Revenue by Geography
    Key Requirements:
    - Extract all available geographic revenue allocations
    - Include:
        * Country-specific breakdowns where available
        * Regional groupings as presented
        * Sub-regional details if provided
    - Maintain the company's original geographic classifications
    - Standardize region names while preserving specific country mentions

    Validation Rules:
    1. All amounts must:
    - Be converted to millions USD if presented differently
    - Match the total revenue across both perspectives
    - Be rounded to 2 decimal places

    2. Item names must be:
    - Unique within each perspective
    - Free of redundant qualifiers
    - Consistent with original filing terminology

    3. Completeness checks:
    - Sum of items must equal the reported total
    - Both perspectives must be attempted
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
    # symbols = ['RTX', 'CROX', 'BYND', 'ROKU', 'ETSY', 'FUBO', 'SDC', 'SHAK', 'GPRO', 'BOOT', 'ADI', 
    #           'TXN', 'ADSK', 'SHW', 'CMG', 'LULU', 'SQ', 'PYPL', 'DOCU', 'MDB', 'DDOG', 'CRWD', 'ZM', 
    #           'HOOD', 'AAPL', 'MSFT', 'AMZN', 'GOOGL', 'TSLA', 'BRK.B', 'META', 'V', 'JPM', 'JNJ', 
    #           'WMT', 'PG', 'UNH', 'XOM']
    symbols = ['XOM']
    
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
                
            summarized_text = llm_think_and_explain_revenue(symbol, filepath)

            console = Console()

            console.print(Panel.fit(
                summarized_text,
                title="[bold blue]Revenue Analysis Summary[/bold blue]",
                border_style="blue",
                padding=(1, 2)
            ))

            response = llm_extraction_from_summarized(symbol, summarized_text)
            
            # Print response in a beautiful format
            console.print(response)
            
            # Save response to JSON file
            output_file = output_dir / f"{symbol}-rev.json"
            # # First get the JSON string
            json_data = response.model_dump_json()
            # # Then write it to file
            with open(output_file, 'w') as f:
                f.write(json_data)
            
        except Exception as e:
            rprint(f"[bold red]Error processing {symbol}:[/bold red] {str(e)}")
    
if __name__ == "__main__":
    main()

