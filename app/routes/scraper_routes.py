from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import json
import os
import time
import logging
from pydantic import BaseModel
from app.services import scraper_locations as locations_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scraper", tags=["scraper"])

class ScrapeStartRequest(BaseModel):
    country: str
    regions: List[str]
    cities: Optional[List[str]] = []

@router.get("/locations/countries")
async def list_countries():
    """List available countries."""
    try:
        return await locations_service.get_countries()
    except locations_service.LocationProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))

@router.get("/locations/regions")
async def list_regions(country: str = Query(..., description="Country code (CCA2)")):
    """List states/provinces for a country."""
    try:
        return await locations_service.get_regions(country)
    except locations_service.LocationProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))

@router.get("/locations/cities")
async def list_cities(
    country: str = Query(..., description="Country code (CCA2)"),
    state: str = Query(..., description="State/Province code (ISO2)")
):
    """List cities for a state."""
    try:
        return await locations_service.get_cities(country, state)
    except locations_service.LocationProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))

@router.post("/start")
async def start_scrape(request: ScrapeStartRequest):
    """Trigger a manual scrape with specified locations."""
    try:
        # Resolve names for better search and human-readable config
        countries = await locations_service.get_countries()
        country_obj = next((c for c in countries if c["code"] == request.country), None)
        country_name = country_obj["name"] if country_obj else request.country
        
        region_names = []
        city_names = request.cities or []
        
        if request.regions:
            all_regions = await locations_service.get_regions(request.country)
            for r_code in request.regions:
                r_obj = next((r for r in all_regions if r["code"] == r_code), None)
                r_name = r_obj["name"] if r_obj else r_code
                region_names.append(r_name)
                
                # AUTO-SATURATION: If no cities selected, fetch ALL cities for this region
                if not request.cities:
                    try:
                        cities_data = await locations_service.get_cities(request.country, r_code)
                        extracted_cities = [c["name"] for c in cities_data]
                        city_names.extend(extracted_cities)
                        logger.info(f"DEBUG: Found {len(extracted_cities)} cities for {r_name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Warning: Failed to auto-fetch cities for {r_name}: {e}")

        # Build search locations using the expanded list of cities
        search_locations = locations_service.build_search_locations(
            country_name, region_names, city_names
        )
        logger.info(f"DEBUG: Total search locations built: {len(search_locations)}")
        
        # Prepare config with names
        config = {
            "country": country_name,
            "regions": region_names,
            "cities": city_names,
            "search_locations": search_locations,
            "timestamp": time.time()
        }
        
        # Ensure directory exists
        config_dir = "data/manual_scrape_configs"
        os.makedirs(config_dir, exist_ok=True)
        
        # Write config to file (manual run history)
        timestamp = int(time.time())
        config_path = f"{config_dir}/scrape_config_{timestamp}.json"
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
            
        # ALSO save to master locations file for continuous scraper / orchestrator
        master_locations_path = "data/scraper_locations.json"
        with open(master_locations_path, "w") as f:
            # We only save the flat list of strings as expected by the scraper
            json.dump(search_locations, f, indent=2)
        logger.info(f"✅ Master locations saved to: {master_locations_path}")
            
        # Trigger Celery task
        from app.worker.scraper_scheduler import celery_app
        celery_app.send_task("run_carpentry_scraper_with_config", args=[config_path])
        
        return {"status": "started", "config_path": config_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start scrape: {str(e)}")
