"""
Email Service - Amazon SES via boto3 SDK
Replaces SMTP-based sending entirely.

Why boto3 over SMTP:
  - Direct AWS API call over HTTPS — never blocked by firewalls
  - Richer error codes (MessageRejected, MailFromDomainNotVerified, etc.)
  - Automatic retry/backoff handled by botocore
  - No TCP connection management or timeout issues

Required .env vars:
  AWS_ACCESS_KEY_ID       — from IAM user ses-sender
  AWS_SECRET_ACCESS_KEY   — from IAM user ses-sender
  AWS_REGION              — e.g. us-east-1
  FROM_EMAIL              — must be verified in SES
  FROM_NAME               — display name
  SES_CONFIGURATION_SET   — e.g. my-config-set (for bounce/complaint tracking)

IMAP (inbound replies) is unchanged — still uses Hostinger/Google Workspace.
"""

import boto3
import logging
import os
import imaplib
import time
import email as email_lib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SES configuration — all from environment variables
# ─────────────────────────────────────────────────────────────────────────────
AWS_REGION            = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID     = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
FROM_EMAIL            = os.getenv("FROM_EMAIL")
FROM_NAME             = os.getenv("FROM_NAME", "Advanced Autonomics")
SES_CONFIGURATION_SET = os.getenv("SES_CONFIGURATION_SET", "my-config-set")

# ─────────────────────────────────────────────────────────────────────────────
# IMAP configuration — unchanged, still used for reading replies
# ─────────────────────────────────────────────────────────────────────────────
IMAP_HOST     = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT     = int(os.getenv("IMAP_PORT", "993"))
IMAP_USERNAME = os.getenv("IMAP_USERNAME")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

logger.info(f"📧 Email Service: boto3 → SES ({AWS_REGION})")
logger.info(f"   From: {FROM_NAME} <{FROM_EMAIL}>")
logger.info(f"   Config Set: {SES_CONFIGURATION_SET}")
logger.info(f"   IMAP: {IMAP_HOST}:{IMAP_PORT}")


def _get_ses_client():
    """Create and return a boto3 SES client."""
    return boto3.client(
        "ses",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )


class EmailService:

    @staticmethod
    def send_email(
        to_email: str,
        subject: str,
        body: str,
        to_name: Optional[str] = None,
        html_body: Optional[str] = None,
        images: Optional[dict] = None,   # kept for API compatibility, ignored by SES SDK
        attachments: Optional[list] = None,
        save_to_sent: bool = True
    ) -> tuple:
        """
        Send email via Amazon SES boto3 SDK.

        Returns:
            (success: bool, error_message: str | None)
        """
        try:
            # ── Build To address ─────────────────────────────────────────────
            to_address = f"{to_name} <{to_email}>" if to_name else to_email
            from_address = f"{FROM_NAME} <{FROM_EMAIL}>"

            logger.info(f"📤 Sending via SES to {to_email}")

            # ── Build message body ────────────────────────────────────────────
            body_dict = {
                "Text": {
                    "Data": body,
                    "Charset": "UTF-8",
                }
            }

            if html_body:
                body_dict["Html"] = {
                    "Data": html_body,
                    "Charset": "UTF-8",
                }

            # ── Send via SES SDK ──────────────────────────────────────────────
            ses = _get_ses_client()

            send_kwargs = {
                "Source": from_address,
                "Destination": {
                    "ToAddresses": [to_address],
                },
                "Message": {
                    "Subject": {
                        "Data": subject,
                        "Charset": "UTF-8",
                    },
                    "Body": body_dict,
                },
                "ReplyToAddresses": [FROM_EMAIL],
            }

            # Attach configuration set if set — required for bounce/complaint tracking
            if SES_CONFIGURATION_SET:
                send_kwargs["ConfigurationSetName"] = SES_CONFIGURATION_SET

            response = ses.send_email(**send_kwargs)

            message_id = response.get("MessageId", "unknown")
            logger.info(f"✅ SES accepted email — MessageId: {message_id}")

            # ── Save to IMAP Sent folder ──────────────────────────────────────
            if save_to_sent and IMAP_HOST and IMAP_USERNAME:
                try:
                    EmailService._save_to_sent_folder(
                        to_email=to_email,
                        to_name=to_name,
                        subject=subject,
                        body=body,
                        html_body=html_body,
                        message_id=message_id,
                    )
                except Exception as e:
                    # Non-fatal — email was already sent
                    logger.warning(f"⚠️ Could not save to Sent folder: {e}")

            return True, None

        # ── SES-specific errors ───────────────────────────────────────────────
        except ClientError as e:
            code    = e.response["Error"]["Code"]
            message = e.response["Error"]["Message"]

            # Map common SES error codes to clear messages
            error_map = {
                "MessageRejected":              "SES rejected message — check From address is verified",
                "MailFromDomainNotVerified":    "Sending domain not verified in SES",
                "ConfigurationSetDoesNotExist": f"SES config set '{SES_CONFIGURATION_SET}' not found",
                "AccountSendingPausedException":"SES account sending is paused — check AWS console",
                "SendingQuotaExceeded":         "SES daily sending quota exceeded",
                "Throttling":                   "SES throttling — too many requests per second",
            }

            friendly = error_map.get(code, f"SES error {code}: {message}")
            logger.error(f"❌ SES ClientError: {friendly}")
            return False, friendly

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return False, error_msg

    @staticmethod
    def _save_to_sent_folder(
        to_email: str,
        to_name: Optional[str],
        subject: str,
        body: str,
        html_body: Optional[str],
        message_id: str,
    ):
        """
        Save a copy of the sent email to the IMAP Sent folder.
        Hostinger/Google Workspace doesn't auto-save SES outbound mail,
        so we push a copy via IMAP APPEND.
        """
        mail = None
        try:
            # Build MIME message for IMAP storage
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"{FROM_NAME} <{FROM_EMAIL}>"
            msg["To"]      = f"{to_name} <{to_email}>" if to_name else to_email
            msg["Date"]    = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
            msg["Message-ID"] = f"<{message_id}@ses.amazonaws.com>"

            msg.attach(MIMEText(body, "plain", "utf-8"))
            if html_body:
                msg.attach(MIMEText(html_body, "html", "utf-8"))

            # Connect to IMAP
            mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            mail.sock.settimeout(30)
            mail.login(IMAP_USERNAME, IMAP_PASSWORD)

            # Find Sent folder
            sent_folders = ["Sent", "INBOX.Sent", "[Gmail]/Sent Mail", "Sent Messages"]
            status, folders = mail.list()
            available = []
            if status == "OK":
                for f in folders:
                    try:
                        available.append(f.decode().split('"')[-2])
                    except:
                        pass

            sent_folder = None
            for candidate in sent_folders:
                if candidate in available:
                    sent_folder = candidate
                    break

            if not sent_folder:
                for folder in available:
                    if "sent" in folder.lower():
                        sent_folder = folder
                        break

            if not sent_folder:
                sent_folder = "INBOX"

            # Append to Sent folder
            mail.append(
                sent_folder,
                "\\Seen",
                imaplib.Time2Internaldate(time.time()),
                msg.as_bytes()
            )
            logger.info(f"💾 Saved to Sent folder: {sent_folder}")

        except Exception as e:
            logger.warning(f"⚠️ IMAP Sent folder save failed: {e}")
        finally:
            if mail:
                try:
                    mail.logout()
                except:
                    pass

    @staticmethod
    def generate_subject(lead_name: str, company: str) -> str:
        """Generate subject line (unchanged)."""
        if company:
            return f"Pilot Opportunity: Autonomous Handling for {company}"
        return f"Automation Opportunity for {lead_name}"

    @staticmethod
    def test_connection() -> tuple:
        """
        Quick connectivity test — verify SES credentials and sending quota.
        Call this on startup or from a health check endpoint.

        Returns:
            (success: bool, message: str)
        """
        try:
            ses = _get_ses_client()
            quota = ses.get_send_quota()

            max24h   = quota.get("Max24HourSend", 0)
            sent24h  = quota.get("SentLast24Hours", 0)
            max_rate = quota.get("MaxSendRate", 0)

            msg = (
                f"SES connected ✅ | "
                f"Sent last 24h: {int(sent24h)}/{int(max24h)} | "
                f"Max rate: {max_rate}/sec"
            )
            logger.info(msg)
            return True, msg

        except ClientError as e:
            msg = f"SES connection failed: {e.response['Error']['Code']}"
            logger.error(msg)
            return False, msg

        except Exception as e:
            msg = f"SES connection error: {str(e)}"
            logger.error(msg)
            return False, msg