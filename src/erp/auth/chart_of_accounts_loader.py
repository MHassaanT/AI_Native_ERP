"""Chart of Accounts Template Loader & Localizer.

Loads localized Chart of Accounts templates from the ERPNext reference repository,
adapts them to the AI-Native ERP schema, and guarantees that essential automated
ledger accounts (Cash, Bank, AR, AP, Inventory, COGS, Revenue, Equity) exist.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from erp.auth.fiscal_years import get_country_info

logger = logging.getLogger(__name__)

# Search paths for reference verified CoA templates
REFERENCE_COA_DIR = Path("/home/hassaan/Desktop/Projects/AI_ERP/refrence/erpnext/erpnext/accounts/doctype/account/chart_of_accounts/verified")


def _normalize_account_type(root_or_type: str) -> str:
    """Normalizes ERPNext root_type or account_type to AI-Native ERP standard."""
    val = (root_or_type or "").upper()
    if any(k in val for k in ["ASSET", "APPLICATION OF FUNDS"]):
        return "ASSET"
    if any(k in val for k in ["LIABILITY", "SOURCE OF FUNDS"]):
        return "LIABILITY"
    if "EQUITY" in val:
        return "EQUITY"
    if any(k in val for k in ["INCOME", "REVENUE"]):
        return "REVENUE"
    if "EXPENSE" in val:
        return "EXPENSE"
    return "ASSET"


def get_available_charts_for_country(country: str) -> list[str]:
    """Returns a list of Chart of Accounts template names applicable for a given country."""
    info = get_country_info(country)
    country_code = info.get("country_code", "").lower()
    country_lower = country.lower().replace(" ", "_")

    chart_names = []

    if REFERENCE_COA_DIR.exists():
        for file in REFERENCE_COA_DIR.glob("*.json"):
            fname = file.name.lower()
            if fname.startswith(f"{country_code}_") or fname.startswith(f"{country_lower}_") or fname.startswith(country_lower):
                try:
                    with open(file, encoding="utf-8") as f:
                        data = json.load(f)
                        name = data.get("name")
                        if name and name not in chart_names:
                            chart_names.append(name)
                except Exception as e:
                    logger.warning("Failed to parse CoA file %s: %s", file, e)

    # Standard options always available
    if f"{country} - Standard GAAP" not in chart_names:
        chart_names.append(f"{country} - Standard GAAP")
    if "Standard GAAP (Universal)" not in chart_names:
        chart_names.append("Standard GAAP (Universal)")
    if "Standard with Numbers" not in chart_names:
        chart_names.append("Standard with Numbers")

    return chart_names


def _slugify_code(name: str, number: str | None = None) -> str:
    """Generates an uppercase alphanumeric account code."""
    if number and number.strip():
        num = re.sub(r"[^0-9A-Z-]", "", number.strip().upper())
        clean_name = re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")
        return f"{num}-{clean_name[:16]}".strip("-")
    clean = re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")
    return clean[:32]


def load_chart_tree(template_name: str, country: str) -> dict[str, Any] | None:
    """Attempts to find and parse the JSON tree for the given template name."""
    if REFERENCE_COA_DIR.exists():
        for file in REFERENCE_COA_DIR.glob("*.json"):
            try:
                with open(file, encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("name") == template_name:
                        return data.get("tree")
            except Exception:
                continue
    return None


def get_standard_gaap_tree(country: str, currency: str) -> list[dict[str, Any]]:
    """Universal standard GAAP double-entry accounts with country/currency adaptations."""
    return [
        {
            "account_code": "1010-CASH",
            "account_name": f"Operating Cash ({currency})",
            "account_type": "ASSET",
            "parent_account_code": None,
        },
        {
            "account_code": "1020-BANK-OPERATING",
            "account_name": f"Primary Operating Bank Account ({currency})",
            "account_type": "ASSET",
            "parent_account_code": None,
        },
        {
            "account_code": "1200-AR-CUSTOMERS",
            "account_name": "Accounts Receivable - Trade Customers",
            "account_type": "ASSET",
            "parent_account_code": None,
        },
        {
            "account_code": "1300-RAW-MATERIALS",
            "account_name": "Raw Materials & Components Inventory",
            "account_type": "ASSET",
            "parent_account_code": None,
        },
        {
            "account_code": "1350-FINISHED-GOODS",
            "account_name": "Finished Goods Valuation",
            "account_type": "ASSET",
            "parent_account_code": None,
        },
        {
            "account_code": "1400-FINISHED-GOODS",
            "account_name": "Finished Goods Inventory Valuation",
            "account_type": "ASSET",
            "parent_account_code": None,
        },
        {
            "account_code": "1500-TAX-ASSETS",
            "account_name": f"Input VAT / Sales Tax Recoverable ({country})",
            "account_type": "ASSET",
            "parent_account_code": None,
        },
        {
            "account_code": "2100-AP-VENDORS",
            "account_name": "Accounts Payable - Trade Vendors",
            "account_type": "LIABILITY",
            "parent_account_code": None,
        },
        {
            "account_code": "2110-AP-EMPLOYEES",
            "account_name": "Accounts Payable - Employee Expense Claims",
            "account_type": "LIABILITY",
            "parent_account_code": None,
        },
        {
            "account_code": "2200-TAX-PAYABLE",
            "account_name": f"Output VAT / Sales Tax Payable ({country})",
            "account_type": "LIABILITY",
            "parent_account_code": None,
        },
        {
            "account_code": "3000-EQUITY-CAPITAL",
            "account_name": "Shareholders Paid-In Capital",
            "account_type": "EQUITY",
            "parent_account_code": None,
        },
        {
            "account_code": "4000-REV-SALES",
            "account_name": "Commercial Sales Revenue",
            "account_type": "REVENUE",
            "parent_account_code": None,
        },
        {
            "account_code": "4000-SALES-REVENUE",
            "account_name": "Commercial Sales Revenue Standard",
            "account_type": "REVENUE",
            "parent_account_code": None,
        },
        {
            "account_code": "5000-COGS-MATERIALS",
            "account_name": "Cost of Goods Sold - Materials",
            "account_type": "EXPENSE",
            "parent_account_code": None,
        },
        {
            "account_code": "5100-EXP-TRAVEL",
            "account_name": "Employee Travel & Operational Expenses",
            "account_type": "EXPENSE",
            "parent_account_code": None,
        },
        {
            "account_code": "5200-DEP-MACHINERY",
            "account_name": "Machine Depreciation Expense",
            "account_type": "EXPENSE",
            "parent_account_code": None,
        },
    ]


def build_accounts_from_template(
    template_name: str,
    country: str,
    currency: str,
) -> list[dict[str, Any]]:
    """Builds a flat list of accounts suitable for inserting into chart_of_accounts table.

    Parses the localized reference JSON template if available, or falls back to
    the standard GAAP tree with country/currency adaptations.
    Guarantees that all required autonomous accounts are present.
    """
    tree = load_chart_tree(template_name, country)
    if not tree:
        return get_standard_gaap_tree(country, currency)

    accounts_list: list[dict[str, Any]] = []
    seen_codes: set[str] = set()

    def _traverse(node: dict[str, Any], parent_code: str | None, current_root_type: str):
        for name, data in node.items():
            if not isinstance(data, dict):
                continue

            root_type = data.get("root_type", current_root_type)
            norm_type = _normalize_account_type(root_type)
            account_number = data.get("account_number")

            code = _slugify_code(name, account_number)
            # Ensure unique code
            orig_code = code
            counter = 1
            while code in seen_codes:
                code = f"{orig_code[:28]}-{counter}"
                counter += 1
            seen_codes.add(code)

            accounts_list.append({
                "account_code": code,
                "account_name": name,
                "account_type": norm_type,
                "currency": currency,
                "parent_account_code": parent_code,
            })

            # Recurse children
            _traverse(data, code, root_type)

    for root_name, root_data in tree.items():
        if isinstance(root_data, dict):
            root_type = root_data.get("root_type", root_name)
            norm_type = _normalize_account_type(root_type)
            root_code = _slugify_code(root_name, root_data.get("account_number"))
            seen_codes.add(root_code)

            accounts_list.append({
                "account_code": root_code,
                "account_name": root_name,
                "account_type": norm_type,
                "currency": currency,
                "parent_account_code": None,
            })
            _traverse(root_data, root_code, root_type)

    # Invariant safety: Ensure our system core accounts exist so automated agents never fail
    required_core_accounts = get_standard_gaap_tree(country, currency)
    for req in required_core_accounts:
        if req["account_code"] not in seen_codes:
            accounts_list.append(req)
            seen_codes.add(req["account_code"])

    return accounts_list
