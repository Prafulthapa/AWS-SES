"""
Celery Bridge - Push scraped carpentry leads to email queue
UPDATED: Only sends VERIFIED emails (found on websites)
UPDATED FOR USA MARKETS (Texas focus)
"""

from celery import Celery
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🛑 PAUSE FLAG - Set to False to only scrape WITHOUT sending to email queue
AUTO_PUSH_TO_QUEUE = os.getenv("AUTO_PUSH_TO_QUEUE", "true").lower() == "true"

# 🔥 NEW: Only send verified emails (found on websites, not guessed)
ONLY_SEND_VERIFIED_EMAILS = os.getenv("ONLY_SEND_VERIFIED_EMAILS", "true").lower() == "true"

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "lead_scraper_bridge",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_routes={
        "process_scraped_lead": {"queue": "emails"},
        "import_carpentry_lead": {"queue": "emails"}
    }
)


def push_lead_to_email_queue(lead_data):
    """
    Push a carpentry lead to email queue.

    Args:
        lead_data: Dict with carpentry lead info
            {
                'company_name': str,
                'executive_name': str,
                'email': str,
                'email_verified': bool,  # 🔥 NEW: Is email real or guessed?
                'phone': str,
                'website': str,
                'address': str,
                'state': str,  # OH, PA, MI, etc.
                'source': str
            }
    """
    try:
        # 🔥 NEW: Skip unverified emails
        if ONLY_SEND_VERIFIED_EMAILS:
            if not lead_data.get('email_verified', False):
                logger.debug(f"⏭️  Skipping {lead_data.get('company_name')} - unverified email (guessed)")
                return None
        
        # Validate required fields
        if not lead_data.get('email'):
            logger.warning(f"⚠️ Skipping {lead_data.get('company_name')} - no email")
            return None

        if '@' not in lead_data.get('email', ''):
            logger.warning(f"⚠️ Skipping {lead_data.get('company_name')} - invalid email")
            return None
#***********************************
        # Format location - USA state or "USA" as default
        state = lead_data.get('state', '').strip()
        if state:
            # If we have a state code (OH, PA, etc.), use it
            location = f"{state}, USA"
        else:
            # Default to USA if no state specified
            location = "USA"

        # Format for email system
        email_task_data = {
            'email': lead_data.get('email'),
            'company': lead_data.get('company_name'),
            'name': lead_data.get('executive_name', 'Manager'),
            'phone': lead_data.get('phone', ''),
            'website': lead_data.get('website', ''),
            'location': location,
            'source': lead_data.get('source', 'Web Scraping'),
            'industry': 'Carpentry/Woodworking',
            'email_verified': lead_data.get('email_verified', False)  # 🔥 NEW: Track quality
        }

        # Send to email worker
        task = celery_app.send_task(
            "process_scraped_lead",
            args=[email_task_data],
            queue="emails",
            countdown=5
        )

        # Show verification status in log
        verified_emoji = "✅" if lead_data.get('email_verified') else "⚠️"
        logger.info(f"{verified_emoji} Queued: {lead_data.get('company_name')} ({location}) → {task.id}")
        return task.id

    except Exception as e:
        logger.error(f"❌ Failed to queue {lead_data.get('company_name')}: {e}")
        return None


def push_leads_batch(leads_list):
    """
    Push multiple carpentry leads in batch.

    Args:
        leads_list: List of lead dicts

    Returns:
        int: Number of leads successfully queued
    """
    
    # 🛑 CHECK PAUSE FLAG
    if not AUTO_PUSH_TO_QUEUE:
        logger.info("=" * 70)
        logger.info("🛑 AUTO_PUSH_TO_QUEUE = False")
        logger.info("📊 SCRAPING ONLY MODE - No emails will be sent")
        logger.info(f"💾 {len(leads_list)} leads collected and saved to JSON")
        logger.info("✅ Data collection complete!")
        logger.info("=" * 70)
        return 0  # No leads queued
    
    # 🔥 NEW: Count verified vs unverified
    verified_leads = [l for l in leads_list if l.get('email_verified', False)]
    unverified_leads = [l for l in leads_list if not l.get('email_verified', False)]
    
    logger.info(f"📤 Pushing carpentry leads to email queue...")
    logger.info(f"   Total leads: {len(leads_list)}")
    logger.info(f"   ✅ Verified (scraped from websites): {len(verified_leads)}")
    logger.info(f"   ⚠️  Unverified (generated guesses): {len(unverified_leads)}")
    
    if ONLY_SEND_VERIFIED_EMAILS:
        logger.info(f"   🔥 ONLY_SEND_VERIFIED_EMAILS = True")
        logger.info(f"   → Will only send to {len(verified_leads)} verified emails")
        logger.info(f"   → Skipping {len(unverified_leads)} unverified emails")

    queued_count = 0
    failed_count = 0
    skipped_unverified = 0

    # Track states for reporting
    state_counts = {}

    for lead in leads_list:
        # Track if skipped due to verification
        if ONLY_SEND_VERIFIED_EMAILS and not lead.get('email_verified', False):
            skipped_unverified += 1
            continue
            
        task_id = push_lead_to_email_queue(lead)
        if task_id:
            queued_count += 1
            # Track state distribution
            state = lead.get('state', 'Unknown')
            state_counts[state] = state_counts.get(state, 0) + 1
        else:
            failed_count += 1

    logger.info(f"")
    logger.info(f"✅ Queued: {queued_count}/{len(leads_list)} leads")
    
    if skipped_unverified > 0:
        logger.info(f"⏭️  Skipped: {skipped_unverified} unverified emails")
    
    if state_counts:
        logger.info(f"📊 State distribution:")
        for state, count in sorted(state_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"   - {state}: {count} leads")
    
    if failed_count > 0:
        logger.warning(f"⚠️ Failed: {failed_count} leads")

    return queued_count