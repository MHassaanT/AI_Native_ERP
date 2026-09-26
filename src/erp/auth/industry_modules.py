"""Industry Vertical Module and Factory Blueprint Mappings.

Derived from ERPNext reference architecture and extended for autonomous manufacturing & commerce.
"""

from typing import TypedDict


class IndustryBlueprint(TypedDict):
    industry_name: str
    default_modules: list[str]
    cost_centers: list[dict[str, str]]
    warehouses: list[dict[str, str]]
    valuation_method: str


INDUSTRY_BLUEPRINTS: dict[str, IndustryBlueprint] = {
    "Manufacturing": {
        "industry_name": "Manufacturing",
        "default_modules": ["accounting", "inventory", "production", "quality", "maintenance", "accounts_payable"],
        "cost_centers": [
            {"code": "PLANT-01", "name": "Main Manufacturing Plant Floor"},
            {"code": "QUALITY-LAB", "name": "Quality Assurance & Metrology Lab"},
            {"code": "CORP-FINANCE", "name": "Corporate Financial Operations"},
            {"code": "COMMERCIAL-SALES", "name": "Industrial Sales & Revenue"},
        ],
        "warehouses": [
            {"code": "WH-RAW-MATERIALS", "name": "Raw Materials Store", "is_quarantine": False},
            {"code": "WH-FINISHED-GOODS", "name": "Finished Goods Central Depot", "is_quarantine": False},
            {"code": "WH-QUARANTINE", "name": "Edge Inspection Quarantine Hold", "is_quarantine": True},
        ],
        "valuation_method": "FIFO",
    },
    "Retail": {
        "industry_name": "Retail",
        "default_modules": ["accounting", "inventory", "commercial", "accounts_payable"],
        "cost_centers": [
            {"code": "STORE-FRONT", "name": "Retail Flagship Storefront"},
            {"code": "ECOMMERCE-OPS", "name": "Online Marketplace Operations"},
            {"code": "CORP-FINANCE", "name": "Corporate Treasury & Accounting"},
        ],
        "warehouses": [
            {"code": "WH-STORE-FRONT", "name": "Storefront Floor Inventory", "is_quarantine": False},
            {"code": "WH-BACKSTOCK", "name": "Retail Stockroom Depot", "is_quarantine": False},
        ],
        "valuation_method": "FIFO",
    },
    "Wholesale / Distribution": {
        "industry_name": "Wholesale / Distribution",
        "default_modules": ["accounting", "inventory", "commercial", "accounts_payable"],
        "cost_centers": [
            {"code": "LOGISTICS-DIST", "name": "Distribution Center Logistics"},
            {"code": "COMMERCIAL-SALES", "name": "B2B Wholesale Accounts"},
            {"code": "CORP-FINANCE", "name": "Corporate Treasury & Accounting"},
        ],
        "warehouses": [
            {"code": "WH-CENTRAL-HUB", "name": "Primary Logistics Distribution Hub", "is_quarantine": False},
            {"code": "WH-IN-TRANSIT", "name": "In-Transit Staging Yard", "is_quarantine": False},
        ],
        "valuation_method": "Moving Average",
    },
    "Services / Consulting": {
        "industry_name": "Services / Consulting",
        "default_modules": ["accounting", "commercial", "workforce"],
        "cost_centers": [
            {"code": "CLIENT-DELIVERY", "name": "Professional Client Engagements"},
            {"code": "CORP-FINANCE", "name": "Corporate Financial Operations"},
            {"code": "COMMERCIAL-SALES", "name": "Consulting Business Development"},
        ],
        "warehouses": [
            {"code": "WH-OFFICE-SUPPLIES", "name": "Office Operational Asset Store", "is_quarantine": False},
        ],
        "valuation_method": "FIFO",
    },
    "Technology / Software": {
        "industry_name": "Technology / Software",
        "default_modules": ["accounting", "commercial", "workforce"],
        "cost_centers": [
            {"code": "ENGINEERING-RD", "name": "Software Engineering & R&D"},
            {"code": "INFRA-CLOUD", "name": "Cloud Infrastructure Operations"},
            {"code": "CORP-FINANCE", "name": "Corporate Finance & Capital"},
            {"code": "SALES-GTM", "name": "Go-To-Market & Revenue"},
        ],
        "warehouses": [
            {"code": "WH-IT-HARDWARE", "name": "Internal Hardware & Lab Equipment", "is_quarantine": False},
        ],
        "valuation_method": "FIFO",
    },
    "Construction / Real Estate": {
        "industry_name": "Construction / Real Estate",
        "default_modules": ["accounting", "inventory", "workforce", "accounts_payable"],
        "cost_centers": [
            {"code": "PROJECT-SITE-01", "name": "Active Job Site 01"},
            {"code": "EQUIPMENT-HEAVY", "name": "Heavy Machinery & Fleet Yard"},
            {"code": "CORP-FINANCE", "name": "Corporate Financial Operations"},
        ],
        "warehouses": [
            {"code": "WH-YARD-SITE", "name": "On-Site Building Materials Yard", "is_quarantine": False},
            {"code": "WH-CENTRAL-DEPOT", "name": "Central Equipment Depot", "is_quarantine": False},
        ],
        "valuation_method": "FIFO",
    },
    "Food & Beverage": {
        "industry_name": "Food & Beverage",
        "default_modules": ["accounting", "inventory", "production", "quality", "accounts_payable"],
        "cost_centers": [
            {"code": "PROCESSING-KITCHEN", "name": "Commercial Kitchen & Processing"},
            {"code": "COLD-CHAIN-LOGISTICS", "name": "Refrigerated Logistics Fleet"},
            {"code": "CORP-FINANCE", "name": "Corporate Financial Controller"},
        ],
        "warehouses": [
            {"code": "WH-COLD-STORAGE", "name": "Temperature-Controlled Perishables Store", "is_quarantine": False},
            {"code": "WH-DRY-GOODS", "name": "Ambient Bulk Ingredients Depot", "is_quarantine": False},
            {"code": "WH-QUARANTINE", "name": "HACCP Inspection Hold", "is_quarantine": True},
        ],
        "valuation_method": "FIFO",
    },
    "Healthcare": {
        "industry_name": "Healthcare",
        "default_modules": ["accounting", "inventory", "workforce", "quality"],
        "cost_centers": [
            {"code": "CLINICAL-OPS", "name": "Clinical Patient Services"},
            {"code": "PHARMACY-DEPOT", "name": "Pharmacy Dispensation Operations"},
            {"code": "CORP-FINANCE", "name": "Hospital Administration & Finance"},
        ],
        "warehouses": [
            {"code": "WH-PHARMACY-VAULT", "name": "Regulated Pharmaceutical Vault", "is_quarantine": False},
            {"code": "WH-MEDICAL-SUPPLIES", "name": "Consumables & Surgical Supply Store", "is_quarantine": False},
        ],
        "valuation_method": "FIFO",
    },
    "Other": {
        "industry_name": "Other",
        "default_modules": ["accounting", "inventory", "commercial", "accounts_payable"],
        "cost_centers": [
            {"code": "OPS-GENERAL", "name": "General Enterprise Operations"},
            {"code": "CORP-FINANCE", "name": "Corporate Financial Controller"},
            {"code": "COMMERCIAL-SALES", "name": "Commercial Revenue"},
        ],
        "warehouses": [
            {"code": "WH-MAIN-01", "name": "Primary Central Warehouse", "is_quarantine": False},
        ],
        "valuation_method": "FIFO",
    },
}


ALL_MODULES = [
    {"slug": "accounting", "name": "General Ledger & Accounting", "icon": "BookOpen", "description": "Deterministic double-entry GL, zero-sum verification & financial periods"},
    {"slug": "inventory", "name": "Inventory & Stock Levels", "icon": "Package", "description": "Real-time stock ledger, stochastic ROP calculator & warehouse partitions"},
    {"slug": "production", "name": "Production & Work Orders", "icon": "Wrench", "description": "Shop floor workstations, BOM hierarchies & OR-Tools CP-SAT scheduling"},
    {"slug": "commercial", "name": "Commercial & Sales", "icon": "TrendingUp", "description": "Customer CRM, margin-defended dynamic pricing, sales orders & PDF quotes"},
    {"slug": "accounts_payable", "name": "Accounts Payable & P2P", "icon": "FileCheck", "description": "Vendor directory, purchase orders, goods receipts & 3-way matching"},
    {"slug": "workforce", "name": "Workforce & Compliance", "icon": "Users", "description": "Staff roster, operator safety certifications, shifts & receipt auditing"},
    {"slug": "quality", "name": "Edge Quality Control", "icon": "ShieldCheck", "description": "Live optical inspection, PLC scrap diverter tripping & lot quarantine"},
    {"slug": "maintenance", "name": "Predictive Maintenance", "icon": "Activity", "description": "Vibration/thermal anomaly detection & automated ticket dispatch"},
]


def get_industry_blueprint(industry: str) -> IndustryBlueprint:
    """Returns the blueprint for an industry, falling back to 'Other'."""
    return INDUSTRY_BLUEPRINTS.get(industry, INDUSTRY_BLUEPRINTS["Other"])
