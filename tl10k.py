# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "edgartools",
#     "openai",
# ]
# ///

import os
from pathlib import Path
from typing import TypeVar, Type
from edgar import *
from openai import OpenAI
from pydantic import BaseModel
import json
import re
from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich import print as rprint

from models import (
    PromptType,
    BusinessOverview,
    ProductService,
    RiskFactor,
    FutureStrategy,
)

def read_prompt(prompt_type: PromptType) -> str:
    with open(prompt_type.get_path(), 'r') as f:
        return f.read()

T = TypeVar('T', bound=BaseModel)

def get_openai_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENROUTER_TOKEN"),
        base_url="https://openrouter.ai/api/v1"
    )

def generate_completion(prompt: str, response_model: Type[T], system_prompt: str = "You are a helpful 10-K summarize assistant.") -> T:
    client = get_openai_client()
    response = client.chat.completions.create(
        model="google/gemini-2.0-flash-001",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    )

    content = response.choices[0].message.content
    
    json_match = re.search(r'```json\n(.+?)\n```', content, re.DOTALL)

    if json_match:
        json_str = json_match.group(1)
        try:
            json_data = json.loads(json_str)
            # Handle list types
            if hasattr(response_model, '__origin__') and response_model.__origin__ is list:
                item_type = response_model.__args__[0]
                return [item_type.model_validate(item) for item in json_data]
            # Handle single model types
            return response_model.model_validate(json_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}")
        except Exception as e:
            raise ValueError(f"Failed to validate response model: {e}")
    else:
        raise ValueError("No JSON content found in the response")

def get_overview(item1: str, item7: str) -> BusinessOverview:
    prompt = read_prompt(PromptType.OVERVIEW)
    prompt = prompt.replace("{item1}", item1).replace("{item7}", item7)
    return generate_completion(prompt, BusinessOverview)

def get_products_and_services(item1: str) -> list[ProductService]:
    prompt = read_prompt(PromptType.PRODUCTS_AND_SERVICES)
    prompt = prompt.replace("{item1}", item1)
    return generate_completion(prompt, list[ProductService])

def get_risk_factors(item1: str) -> list[RiskFactor]:
    prompt = read_prompt(PromptType.RISK_FACTORS)
    prompt = prompt.replace("{item1}", item1)
    return generate_completion(prompt, list[RiskFactor])

def get_strategies_and_future_plans(item1: str, item7: str) -> list[FutureStrategy]:
    prompt = read_prompt(PromptType.STRATEGIES_AND_FUTURE_PLANS)
    prompt = prompt.replace("{item1}", item1).replace("{item7}", item7)
    return generate_completion(prompt, list[FutureStrategy])

def get_summarize(symbol: str, console: Console) -> dict:
    # Set Edgar identity
    set_identity(os.getenv("EDGAR_IDENTITY"))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        # Initialize progress
        fetch_task = progress.add_task(f"[cyan]Fetching 10-K filing for {symbol}...", total=None)
        
        company = Company(symbol)
        filing = company.latest("10-K")

        if not filing:
            progress.stop()
            console.print(f"[red]No 10-K filing found for {symbol}[/red]")
            return None

        filing_url = filing.filing_url        
        progress.update(fetch_task, description=f"[green]Found 10-K filing: {filing_url}[/green]")
        ten_k = filing.obj()

        item_1 = ten_k["ITEM 1"]
        item_1A = ten_k["ITEM 1A"]
        item_1_merged = item_1 + "\n\n" + item_1A
        item_7 = ten_k["ITEM 7"]
        
        # Update progress for each step
        progress.update(fetch_task, description="[yellow]Analyzing business overview...[/yellow]")
        business_overview = get_overview(item_1, item_7)
        
        progress.update(fetch_task, description="[yellow]Analyzing products and services...[/yellow]")
        products_and_services = get_products_and_services(item_1)
        
        progress.update(fetch_task, description="[yellow]Analyzing risk factors...[/yellow]")
        risk_factors = get_risk_factors(item_1A)
        
        progress.update(fetch_task, description="[yellow]Analyzing strategies and future plans...[/yellow]")
        strategies_and_future_plans = get_strategies_and_future_plans(item_1_merged, item_7)
        
        progress.update(fetch_task, description="[green]Analysis completed![/green]")

    summary = {
        "symbol": symbol,
        "filing_url": filing_url,
        "business_overview": business_overview.model_dump(),
        "products_and_services": [p.model_dump() for p in products_and_services],
        "risk_factors": [r.model_dump() for r in risk_factors],
        "strategies_and_future_plans": [s.model_dump() for s in strategies_and_future_plans]
    }

    return summary


def save_result(symbol: str, result: dict, console: Console) -> None:
    """Save the result to a JSON file in the outputs directory.
    
    Args:
        symbol: The stock symbol
        result: The data to save
        console: Rich console instance
    """
    output_path = Path("outputs") / f"{symbol}.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    console.print(f"[green]Summary written to {output_path}[/green]")

def main():
    # Initialize rich console
    console = Console()
    
    # Show welcome message
    console.print(Panel.fit(
        "[bold cyan]10-K Filing Analyzer[/bold cyan]\n"
        "[dim]Analyze company filings and generate comprehensive summaries[/dim]",
        border_style="cyan"
    ))
    
    try:
        # Get symbol from user
        symbol = Prompt.ask("\nEnter company symbol", console=console)
        symbol = symbol.upper()
        
        # Show processing message
        console.print(f"\n[bold]Processing {symbol}...[/bold]")
        
        # Process the filing
        result = get_summarize(symbol, console)
        if result:
            save_result(symbol, result, console)
            console.print("\n[bold green]✓ Analysis completed successfully![/bold green]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Process cancelled by user[/yellow]")
        exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error occurred:[/bold red] {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()