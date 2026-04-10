import httpx
from functools import lru_cache
import os
from typing import List, Dict, Any

class LocationProviderError(Exception):
    """Exception raised for external API failures."""
    pass

CSC_API_KEY = os.getenv("CSC_API_KEY")

async def get_countries() -> List[Dict[str, str]]:
    """Fetch all countries from restcountries.com."""
    url = "https://restcountries.com/v3.1/all?fields=name,cca2"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            countries = [
                {"code": country.get("cca2"), "name": country.get("name", {}).get("common")}
                for country in data
            ]
            # Filter out any None values and sort
            countries = [c for c in countries if c["code"] and c["name"]]
            return sorted(countries, key=lambda x: x["name"])
    except Exception as e:
        raise LocationProviderError(f"Failed to fetch countries: {str(e)}")

async def get_regions(country_code: str) -> List[Dict[str, str]]:
    """Fetch states/provinces for a country from countrystatecity.in."""
    url = f"https://api.countrystatecity.in/v1/countries/{country_code}/states"
    headers = {"X-CSCAPI-KEY": CSC_API_KEY or ""}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            regions = [
                {"code": state.get("iso2"), "name": state.get("name")}
                for state in data
            ]
            return sorted(regions, key=lambda x: x["name"])
    except Exception as e:
        raise LocationProviderError(f"Failed to fetch regions for {country_code}: {str(e)}")

async def get_cities(country_code: str, state_code: str) -> List[Dict[str, str]]:
    """Fetch cities for a state in a country from countrystatecity.in."""
    url = f"https://api.countrystatecity.in/v1/countries/{country_code}/states/{state_code}/cities"
    headers = {"X-CSCAPI-KEY": CSC_API_KEY or ""}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            cities = [
                {"code": city.get("name"), "name": city.get("name")}
                for city in data
            ]
            return sorted(cities, key=lambda x: x["name"])
    except Exception as e:
        raise LocationProviderError(f"Failed to fetch cities for {country_code}/{state_code}: {str(e)}")

import unicodedata
import re

def clean_city_name(name: str) -> str:
    """Normalize city name by removing administrative prefixes and converting to ASCII."""
    if not name:
        return ""
    
    # Remove administrative prefixes (case-insensitive)
    # Examples: "District of...", "County of...", "Srŏk Malai"
    name = re.sub(r'^(sr[oŏ]k|district|county|region|municipality|city of|town of)\s+', '', name, flags=re.IGNORECASE)
    
    # Also handle some suffixes if they appear at the end
    name = re.sub(r'\s+(district|county|region|municipality)$', '', name, flags=re.IGNORECASE)

    # Normalize unicode to ASCII (e.g., é -> e, ŏ -> o)
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')

    # Strip whitespace and normalize spaces
    name = " ".join(name.split())
    return name.strip()

def build_search_locations(country_name: str, state_names: List[str], city_names: List[str]) -> List[str]:
    """
    Formatted location list for scraper using cleaned full names.
    Returns a list of strings like "City, State, Country" or "State, Country".
    """
    locations = []
    
    if city_names and len(city_names) > 0:
        for city in city_names:
            cleaned_city = clean_city_name(city)
            state_suffix = f", {state_names[0]}" if state_names else ""
            locations.append(f"{cleaned_city}{state_suffix}, {country_name}")
    else:
        for state in state_names:
            locations.append(f"{state}, {country_name}")
            
    return locations
