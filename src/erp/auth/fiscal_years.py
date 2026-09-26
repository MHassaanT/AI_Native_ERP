"""Country Localization Metadata: Fiscal Years, Currencies, and Timezones.

Ported and enhanced from ERPNext's reference setup data.
"""

from typing import TypedDict


class CountryLocalization(TypedDict):
    country_name: str
    country_code: str
    currency: str
    currency_symbol: str
    timezone: str
    fiscal_year_start: str  # MM-DD
    fiscal_year_end: str    # MM-DD


COUNTRY_LOCALIZATIONS: dict[str, CountryLocalization] = {
    "Pakistan": {
        "country_name": "Pakistan",
        "country_code": "pk",
        "currency": "PKR",
        "currency_symbol": "Rs",
        "timezone": "Asia/Karachi",
        "fiscal_year_start": "07-01",
        "fiscal_year_end": "06-30",
    },
    "United States": {
        "country_name": "United States",
        "country_code": "us",
        "currency": "USD",
        "currency_symbol": "$",
        "timezone": "America/New_York",
        "fiscal_year_start": "01-01",
        "fiscal_year_end": "12-31",
    },
    "United Kingdom": {
        "country_name": "United Kingdom",
        "country_code": "gb",
        "currency": "GBP",
        "currency_symbol": "£",
        "timezone": "Europe/London",
        "fiscal_year_start": "04-01",
        "fiscal_year_end": "03-31",
    },
    "India": {
        "country_name": "India",
        "country_code": "in",
        "currency": "INR",
        "currency_symbol": "₹",
        "timezone": "Asia/Kolkata",
        "fiscal_year_start": "04-01",
        "fiscal_year_end": "03-31",
    },
    "United Arab Emirates": {
        "country_name": "United Arab Emirates",
        "country_code": "ae",
        "currency": "AED",
        "currency_symbol": "AED",
        "timezone": "Asia/Dubai",
        "fiscal_year_start": "01-01",
        "fiscal_year_end": "12-31",
    },
    "Saudi Arabia": {
        "country_name": "Saudi Arabia",
        "country_code": "sa",
        "currency": "SAR",
        "currency_symbol": "SAR",
        "timezone": "Asia/Riyadh",
        "fiscal_year_start": "01-01",
        "fiscal_year_end": "12-31",
    },
    "Australia": {
        "country_name": "Australia",
        "country_code": "au",
        "currency": "AUD",
        "currency_symbol": "A$",
        "timezone": "Australia/Sydney",
        "fiscal_year_start": "07-01",
        "fiscal_year_end": "06-30",
    },
    "Canada": {
        "country_name": "Canada",
        "country_code": "ca",
        "currency": "CAD",
        "currency_symbol": "C$",
        "timezone": "America/Toronto",
        "fiscal_year_start": "01-01",
        "fiscal_year_end": "12-31",
    },
    "Germany": {
        "country_name": "Germany",
        "country_code": "de",
        "currency": "EUR",
        "currency_symbol": "€",
        "timezone": "Europe/Berlin",
        "fiscal_year_start": "01-01",
        "fiscal_year_end": "12-31",
    },
    "France": {
        "country_name": "France",
        "country_code": "fr",
        "currency": "EUR",
        "currency_symbol": "€",
        "timezone": "Europe/Paris",
        "fiscal_year_start": "01-01",
        "fiscal_year_end": "12-31",
    },
    "Singapore": {
        "country_name": "Singapore",
        "country_code": "sg",
        "currency": "SGD",
        "currency_symbol": "S$",
        "timezone": "Asia/Singapore",
        "fiscal_year_start": "04-01",
        "fiscal_year_end": "03-31",
    },
    "Netherlands": {
        "country_name": "Netherlands",
        "country_code": "nl",
        "currency": "EUR",
        "currency_symbol": "€",
        "timezone": "Europe/Amsterdam",
        "fiscal_year_start": "01-01",
        "fiscal_year_end": "12-31",
    },
    "New Zealand": {
        "country_name": "New Zealand",
        "country_code": "nz",
        "currency": "NZD",
        "currency_symbol": "NZ$",
        "timezone": "Pacific/Auckland",
        "fiscal_year_start": "04-01",
        "fiscal_year_end": "03-31",
    },
    "South Africa": {
        "country_name": "South Africa",
        "country_code": "za",
        "currency": "ZAR",
        "currency_symbol": "R",
        "timezone": "Africa/Johannesburg",
        "fiscal_year_start": "03-01",
        "fiscal_year_end": "02-28",
    },
    "Turkey": {
        "country_name": "Turkey",
        "country_code": "tr",
        "currency": "TRY",
        "currency_symbol": "₺",
        "timezone": "Europe/Istanbul",
        "fiscal_year_start": "01-01",
        "fiscal_year_end": "12-31",
    },
    "Indonesia": {
        "country_name": "Indonesia",
        "country_code": "id",
        "currency": "IDR",
        "currency_symbol": "Rp",
        "timezone": "Asia/Jakarta",
        "fiscal_year_start": "01-01",
        "fiscal_year_end": "12-31",
    },
    "Mexico": {
        "country_name": "Mexico",
        "country_code": "mx",
        "currency": "MXN",
        "currency_symbol": "Mex$",
        "timezone": "America/Mexico_City",
        "fiscal_year_start": "01-01",
        "fiscal_year_end": "12-31",
    },
    "Brazil": {
        "country_name": "Brazil",
        "country_code": "br",
        "currency": "BRL",
        "currency_symbol": "R$",
        "timezone": "America/Sao_Paulo",
        "fiscal_year_start": "01-01",
        "fiscal_year_end": "12-31",
    },
    "Egypt": {
        "country_name": "Egypt",
        "country_code": "eg",
        "currency": "EGP",
        "currency_symbol": "E£",
        "timezone": "Africa/Cairo",
        "fiscal_year_start": "07-01",
        "fiscal_year_end": "06-30",
    },
    "Bangladesh": {
        "country_name": "Bangladesh",
        "country_code": "bd",
        "currency": "BDT",
        "currency_symbol": "৳",
        "timezone": "Asia/Dhaka",
        "fiscal_year_start": "07-01",
        "fiscal_year_end": "06-30",
    },
}


def get_country_info(country: str) -> CountryLocalization:
    """Returns localization configuration for a given country, falling back to US/Global defaults."""
    if country in COUNTRY_LOCALIZATIONS:
        return COUNTRY_LOCALIZATIONS[country]

    # Case-insensitive search
    for name, data in COUNTRY_LOCALIZATIONS.items():
        if name.lower() == country.lower():
            return data

    # Default fallback
    return {
        "country_name": country,
        "country_code": "global",
        "currency": "USD",
        "currency_symbol": "$",
        "timezone": "UTC",
        "fiscal_year_start": "01-01",
        "fiscal_year_end": "12-31",
    }
