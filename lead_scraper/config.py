"""
Lead Scraper Configuration - CANADA EDITION
Canada-wide carpentry, joinery, woodworking companies
NO LinkedIn - Uses public directories
"""

SCRAPER_CONFIG = {
    # Daily targets
    "daily_target": 500,
    "max_leads_per_source": 200,

    # Geographic focus (100% Canada)
    "geographic_split": {
        "canada": 100,
        "usa": 0,
        "australia": 0,
        "europe": 0
    },

    # Target locations in Canada (All provinces and territories)
    "target_locations": [
        # ONTARIO - Major Cities
        "Toronto ON", "Ottawa ON", "Mississauga ON", "Brampton ON", "Hamilton ON",
        "London ON", "Markham ON", "Vaughan ON", "Kitchener ON", "Windsor ON",
        "Richmond Hill ON", "Oakville ON", "Burlington ON", "Oshawa ON", "Barrie ON",
        "St. Catharines ON", "Cambridge ON", "Waterloo ON", "Guelph ON", "Sudbury ON",
        "Kingston ON", "Whitby ON", "Ajax ON", "Thunder Bay ON", "Pickering ON",
        "Newmarket ON", "Niagara Falls ON", "Peterborough ON", "Sault Ste. Marie ON",
        "Sarnia ON", "Welland ON", "Belleville ON", "North Bay ON", "Cornwall ON",
        "Chatham ON", "Georgetown ON", "St. Thomas ON", "Woodstock ON", "Bowmanville ON",
        "Leamington ON", "Stouffville ON", "Orillia ON", "Stratford ON", "Orangeville ON",
        "Bradford ON", "Timmins ON", "Keswick ON", "Bolton ON", "Midland ON",

        # QUEBEC - Major Cities
        "Montreal QC", "Quebec City QC", "Laval QC", "Gatineau QC", "Longueuil QC",
        "Sherbrooke QC", "Saguenay QC", "Levis QC", "Trois-Rivieres QC", "Terrebonne QC",
        "Saint-Jean-sur-Richelieu QC", "Repentigny QC", "Brossard QC", "Drummondville QC",
        "Saint-Jerome QC", "Granby QC", "Blainville QC", "Saint-Hyacinthe QC",
        "Shawinigan QC", "Dollard-des-Ormeaux QC", "Rimouski QC", "Victoriaville QC",
        "Mirabel QC", "Joliette QC", "Sorel-Tracy QC", "Vaudreuil-Dorion QC",
        "Val-d'Or QC", "Sept-Iles QC", "Alma QC", "Rouyn-Noranda QC",

        # BRITISH COLUMBIA - Major Cities
        "Vancouver BC", "Surrey BC", "Burnaby BC", "Richmond BC", "Abbotsford BC",
        "Coquitlam BC", "Kelowna BC", "Saanich BC", "Delta BC", "Langley BC",
        "Victoria BC", "Kamloops BC", "Nanaimo BC", "Chilliwack BC", "Prince George BC",
        "Vernon BC", "Courtenay BC", "Campbell River BC", "Penticton BC", "Port Coquitlam BC",
        "Maple Ridge BC", "New Westminster BC", "North Vancouver BC", "West Vancouver BC",
        "Port Moody BC", "Cranbrook BC", "Fort St. John BC", "Terrace BC", "Parksville BC",
        "Salmon Arm BC", "Powell River BC", "Williams Lake BC", "Quesnel BC",

        # ALBERTA - Major Cities
        "Calgary AB", "Edmonton AB", "Red Deer AB", "Lethbridge AB", "St. Albert AB",
        "Medicine Hat AB", "Grande Prairie AB", "Airdrie AB", "Spruce Grove AB",
        "Leduc AB", "Fort McMurray AB", "Lloydminster AB", "Camrose AB", "Brooks AB",
        "Cold Lake AB", "Wetaskiwin AB", "Stony Plain AB", "Lacombe AB", "Cochrane AB",
        "Okotoks AB", "High River AB", "Sylvan Lake AB", "Canmore AB", "Whitecourt AB",
        "Hinton AB", "Edson AB", "Beaumont AB", "Drayton Valley AB", "Devon AB",

        # MANITOBA - Major Cities
        "Winnipeg MB", "Brandon MB", "Steinbach MB", "Portage la Prairie MB",
        "Thompson MB", "Selkirk MB", "Dauphin MB", "Morden MB", "Winkler MB",
        "The Pas MB", "Flin Flon MB",

        # SASKATCHEWAN - Major Cities
        "Saskatoon SK", "Regina SK", "Prince Albert SK", "Moose Jaw SK", "Swift Current SK",
        "Yorkton SK", "North Battleford SK", "Estevan SK", "Weyburn SK", "Lloydminster SK",
        "Martensville SK", "Warman SK", "Humboldt SK", "Melfort SK",

        # NOVA SCOTIA - Major Cities
        "Halifax NS", "Dartmouth NS", "Sydney NS", "Truro NS", "New Glasgow NS",
        "Glace Bay NS", "Kentville NS", "Amherst NS", "Bridgewater NS", "Yarmouth NS",
        "Cole Harbour NS", "Lower Sackville NS",

        # NEW BRUNSWICK - Major Cities
        "Moncton NB", "Saint John NB", "Fredericton NB", "Dieppe NB", "Miramichi NB",
        "Bathurst NB", "Edmundston NB", "Campbellton NB", "Quispamsis NB", "Rothesay NB",

        # NEWFOUNDLAND AND LABRADOR
        "St. John's NL", "Mount Pearl NL", "Corner Brook NL", "Conception Bay South NL",
        "Paradise NL", "Grand Falls-Windsor NL", "Gander NL", "Portugal Cove-St. Philip's NL",

        # PRINCE EDWARD ISLAND
        "Charlottetown PE", "Summerside PE", "Stratford PE", "Cornwall PE",

        # TERRITORIES
        "Yellowknife NT", "Whitehorse YT", "Iqaluit NU"
    ],

    # Industries (Carpentry/Woodworking focused)
    "industries": [
        "Carpentry",
        "Finish Carpentry",
        "Framing",
        "Cabinet Making",
        "Woodworking",
        "Millwork",
        "Custom Furniture",
        "Kitchen Remodeling",
        "Bathroom Remodeling",
        "Commercial Carpentry",
        "Residential Construction",
        "Deck Building",
        "Trim Carpentry",
        "Door Installation",
        "Window Installation",
        "Flooring Installation",
        "General Contracting"
    ],

    # Keywords for carpentry/woodworking searches
    "industry_keywords": [
        "carpentry",
        "carpenter",
        "cabinet maker",
        "cabinetmaker",
        "woodworking",
        "finish carpentry",
        "framing contractor",
        "custom carpentry",
        "kitchen remodeling",
        "bathroom remodeling",
        "commercial carpentry",
        "residential carpentry",
        "trim carpenter",
        "millwork",
        "custom woodwork",
        "deck builder",
        "renovation carpentry",
        "custom cabinetry",
        "handyman carpentry",
        "remodeling contractor"
    ],

    # Job titles to find (decision makers)
    "job_titles": [
        "Owner",
        "President",
        "CEO",
        "Founder",
        "Principal",
        "Manager",
        "General Manager",
        "Operations Manager",
        "Business Owner",
        "Lead Carpenter",
        "Master Carpenter",
        "Foreman",
        "Project Manager"
    ],

    # Company sizes (smaller businesses typical for carpentry)
    "company_sizes": [
        "1-10",      # Solo operators & small teams
        "11-50",     # Medium carpentry businesses
        "51-200",    # Larger contractors
    ],

    # Scraping sources
    "scraping_sources": {
        "yellow_pages": True,     # YellowPages.ca
        "google_maps": True,      # Google Maps (best for local businesses)
        "yelp": False,            # Could add later
        "homestars": False        # Could add later
    },

    # Email finding methods
    "email_methods": {
        "scrape_website": True,   # Scrape company website
        "guess_pattern": True,    # Generate from company name
        "smtp_verify": False      # SMTP verification (slow, often blocked)
    },

    # Run schedule (2 AM daily by default)
    "run_schedule": "0 2 * * *",  # Cron format: minute hour day month weekday

    # Rate limiting (be respectful to avoid blocks)
    "delays": {
        "min_delay": 3,              # Minimum delay between requests (seconds)
        "max_delay": 7,              # Maximum delay between requests
        "page_load": 3,              # Wait for page load
        "between_searches": 15,      # Delay between different searches
        "between_sources": 30        # Delay between different sources
    },

    # Scraping limits per run
    "limits": {
        "max_pages_per_search": 3,   # Max pages to scrape per keyword/location
        "max_results_per_page": 50,  # Max results to process per page
        "daily_request_limit": 1000  # Max HTTP requests per day
    },

    # Data quality
    "validation": {
        "require_email": False,       # Don't skip leads without email
        "require_phone": False,       # Don't skip leads without phone
        "require_website": False,     # Don't skip leads without website
        "min_company_name_length": 3  # Minimum characters for company name
    }
}

# Email pattern templates (for generating emails)
EMAIL_PATTERNS = [
    "info@{domain}",
    "contact@{domain}",
    "admin@{domain}",
    "office@{domain}",
    "inquiries@{domain}",
    "sales@{domain}",
    "{first}.{last}@{domain}",
    "{first}@{domain}",
    "{last}@{domain}"
]

# Common Canadian business email domains
COMMON_DOMAINS = [
    ".ca",
    ".com",
    ".net",
    ".org"
]

# Executive title patterns (for extracting names from websites)
EXECUTIVE_TITLES = [
    "Owner",
    "President",
    "CEO",
    "Founder",
    "Principal",
    "Manager",
    "Lead Carpenter",
    "Master Carpenter"
]

# Words to remove from company names when generating emails
COMPANY_NAME_STOPWORDS = [
    "inc", "llc", "ltd", "limited", "corp", "corporation",
    "carpentry", "services", "company", "co", "solutions",
    "group", "contractors", "construction"
]

# Output configuration
OUTPUT_CONFIG = {
    "save_json": True,           # Save raw JSON file
    "save_csv": False,           # Also save CSV? (not needed)
    "json_indent": 2,            # Pretty print JSON
    "include_timestamp": True    # Add timestamp to filenames
}

# Celery/Queue configuration
CELERY_CONFIG = {
    "auto_push_to_queue": True,      # Automatically push to email queue
    "batch_size": 50,                # Process in batches of 50
    "retry_failed": True,            # Retry failed queue pushes
    "max_retries": 3                 # Max retry attempts
}