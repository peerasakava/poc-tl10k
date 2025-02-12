from enum import Enum
from pathlib import Path
from pydantic import BaseModel

class PromptType(Enum):
    OVERVIEW = "overview.txt"
    PRODUCTS_AND_SERVICES = "products_and_services.txt"
    RISK_FACTORS = "risk_factors.txt"
    STRATEGIES_AND_FUTURE_PLANS = "strategies_and_future_plans.txt"

    def get_path(self) -> Path:
        return Path("prompts") / self.value

class BusinessOverview(BaseModel):
    business_description: str
    revenue_model: str
    strategic_direction: str
    long_term_goals: str

class ProductService(BaseModel):
    product_service_name: str
    summary: str
    details: str

class RiskFactor(BaseModel):
    risk_factor_title: str
    summary: str
    details: str

class FutureStrategy(BaseModel):
    future_strategy_focus_headline: str
    summary: str
    management_quote: str
