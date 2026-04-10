"""
Lead Orchestrator - CARPENTRY VERSION
NO LinkedIn - Uses Yellow Pages, True Local, Google Maps
Pushes leads directly to email queue
WITH GRACEFUL SHUTDOWN SUPPORT
"""

import asyncio
import logging
import json
import signal
import sys
from datetime import datetime
from pathlib import Path

# Import the NEW carpentry scraper (not LinkedIn!)
from carpentry_lead_scraper import CarpentryLeadScraper
from celery_bridge import push_leads_batch

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

API_BASE = "http://api:8000"


class LeadOrchestrator:
    """Orchestrate carpentry lead generation pipeline."""

    def __init__(self):
        self.scraper = None
        self.all_leads = []
        self.shutdown_requested = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def handle_shutdown(self, signum, frame):
        """Handle Ctrl+C and other shutdown signals gracefully."""
        logger.info("\n" + "=" * 70)
        logger.info("🛑 SHUTDOWN SIGNAL RECEIVED (Ctrl+C)")
        logger.info("=" * 70)
        
        self.shutdown_requested = True
        
        # Force save current progress
        if self.scraper and self.scraper.all_leads:
            logger.info("💾 Saving progress before exit...")
            try:
                self.scraper.save_progress(force=True)
                logger.info(f"✅ Saved {len(self.scraper.all_leads)} leads successfully")
                logger.info(f"📁 File: {self.scraper.session_file}")
            except Exception as e:
                logger.error(f"❌ Error saving: {e}")
        else:
            logger.info("ℹ️  No leads to save")
        
        logger.info("=" * 70)
        logger.info("👋 Goodbye! Your data is safe.")
        logger.info("=" * 70)
        
        # Cleanup browser
        if self.scraper:
            self.scraper.cleanup()
        
        # Exit cleanly
        sys.exit(0)

    async def run_pipeline(self, locations=None):
        """Run the complete pipeline."""
        logger.info("=" * 70)
        logger.info("🚀 CARPENTRY LEAD PIPELINE STARTING")
        logger.info("=" * 70)
        logger.info("💡 Press Ctrl+C anytime to save and exit safely")
        logger.info("💾 Auto-saves every 500 leads")
        logger.info("=" * 70)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Step 1: Scrape carpentry businesses
        logger.info("=" * 70)
        logger.info("STEP 1: SCRAPING CARPENTRY BUSINESSES")
        logger.info("=" * 70)

        try:
            self.scraper = CarpentryLeadScraper()
            
            # Check for shutdown during scraping
            if self.shutdown_requested:
                logger.info("🛑 Shutdown requested, exiting...")
                return
            
            self.scraper.run_full_scrape(locations=locations)
            self.all_leads = self.scraper.all_leads
            
        except KeyboardInterrupt:
            logger.info("🛑 Interrupted during scraping")
            # Save handled by signal handler
            return
        except Exception as e:
            logger.error(f"❌ Scraping failed: {e}", exc_info=True)
            # Try to save whatever we got
            if self.scraper and self.scraper.all_leads:
                logger.info("💾 Attempting to save partial results...")
                self.scraper.save_progress(force=True)
            return

        logger.info(f"✅ Step 1 complete: {len(self.all_leads)} leads scraped")

        if not self.all_leads:
            logger.warning("⚠️ No leads scraped, pipeline stopping")
            return

        # Step 2: Push to email queue
        logger.info("=" * 70)
        logger.info("STEP 2: PUSH TO EMAIL QUEUE")
        logger.info("=" * 70)

        if self.shutdown_requested:
            logger.info("🛑 Shutdown requested, skipping email queue")
            return

        # Filter leads with emails
        leads_with_email = [
            lead for lead in self.all_leads
            if lead.get('email') and '@' in lead.get('email', '')
        ]

        logger.info(f"📧 Leads with valid emails: {len(leads_with_email)}")

        if leads_with_email:
            try:
                queued = push_leads_batch(leads_with_email)
                logger.info(f"✅ Step 2 complete: {queued} leads queued for emailing")
            except Exception as e:
                logger.error(f"❌ Email queueing failed: {e}")
                queued = 0
        else:
            logger.warning("⚠️ No leads with emails to queue")
            queued = 0

        # Step 3: Save backup
        logger.info("=" * 70)
        logger.info("STEP 3: SAVE BACKUP")
        logger.info("=" * 70)

        backup_file = f"data/carpentry_leads_{timestamp}.json"
        self.save_backup(self.all_leads, backup_file)

        # Print summary
        self.print_summary(queued)

    def save_backup(self, leads, filename):
        """Save leads to JSON backup."""
        logger.info(f"💾 Saving backup to: {filename}")

        Path(filename).parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(leads, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved {len(leads)} leads to backup")
        except Exception as e:
            logger.error(f"❌ Failed to save backup: {e}")

    def print_summary(self, queued_count):
        """Print pipeline summary."""
        logger.info("\n" + "=" * 70)
        logger.info("📊 PIPELINE SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total leads scraped:  {len(self.all_leads)}")
        logger.info(f"Queued for emailing:  {queued_count}")

        # Source breakdown
        sources = {}
        for lead in self.all_leads:
            source = lead.get('source', 'Unknown')
            sources[source] = sources.get(source, 0) + 1

        logger.info("\n🔍 Sources:")
        for source, count in sources.items():
            logger.info(f"  - {source}: {count}")

        # Show session files
        session_files = list(Path("data").glob("session_*.json"))
        if session_files:
            logger.info(f"\n💾 Session files created: {len(session_files)}")
            for f in sorted(session_files, reverse=True)[:3]:  # Show last 3
                try:
                    size_kb = f.stat().st_size / 1024
                    logger.info(f"  - {f.name} ({size_kb:.1f} KB)")
                except:
                    logger.info(f"  - {f.name}")

        logger.info("=" * 70)


async def main():
    """Main execution."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="Path to scrape config JSON")
    args = parser.parse_args()
    
    locations = None
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
                locations = config.get('search_locations')
                if locations:
                    print(f"📂 Loaded {len(locations)} custom locations from config")
        except Exception as e:
            print(f"❌ Failed to load config: {e}")

    orchestrator = LeadOrchestrator()
    
    try:
        await orchestrator.run_pipeline(locations=locations)
    except KeyboardInterrupt:
        logger.info("\n🛑 Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"❌ Pipeline error: {e}", exc_info=True)
    finally:
        logger.info("✅ Pipeline ended")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Already handled by signal handler