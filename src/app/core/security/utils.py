from typing import Dict, Any
from pathlib import Path
import secrets
import string
import math

from passlib.context import CryptContext
from mailersend import emails
from jinja2 import Template

from core.config import settings

mailer = emails.NewEmail(settings.MAILERSEND_API_KEY)

class Hash:
  context = CryptContext(schemes=["argon2"], deprecated="auto")

  @classmethod
  def hash(cls, plain: str) -> str:
    """Return hashed password."""
    return cls.context.hash(secret=plain)
          
  @classmethod
  def verify(cls, plain: str, hashed: str) -> bool:
    """Return bool type of the verified password."""
    return cls.context.verify(secret=plain, hash=hashed)
    
def convert_size(size_bytes: bytes):
  if not bytes:
    return "0B"
  size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
  i = int(math.floor(math.log(size_bytes, 1024)))
  p = math.pow(1024, i)
  s = round(size_bytes / p, 2)
  return "%s %s" % (s, size_name[i])

def render_template(*, template_name: str, context: Dict[str, Any]) -> str:
  template_path = (
    Path(__file__).parent.parent / "templates" / template_name
  ).read_text()
  html_content = Template(template_path).render(context)
  return html_content

def generate_verification_code(length: int = 6):
  # Define character pool
  characters = string.ascii_uppercase + string.digits

  # Remove ambiguous characters
  ambiguous_chars = "0O1I"
  clean_chars = "".join(c for c in characters if c not in ambiguous_chars)

  # Generate cryptographically secure code
  return "".join(secrets.choice(clean_chars) for _ in range(length))

def send_email(to: str, subject: str, html_content: str, text_content: str, reply_to_name: str, **kwargs) -> str:
  # Define an empty dict to populate with mail values
  mail_body = {}

  # Set sender details
  mail_from = {
    "name": settings.MAILERSEND_SMTP_NAME,
    "email": settings.MAILERSEND_SMTP_EMAIL
  }
  
  # Set recipient details
  recipients = [
    {
      "name": "",
      "email": to
    }
  ]
  
  # Set reply-to details
  reply_to = [
    {
      "name": reply_to_name,
      "email": settings.MAILERSEND_SMTP_EMAIL,
    }
  ]

  # Configure email details
  mailer.set_mail_from(mail_from, mail_body)
  mailer.set_mail_to(recipients, mail_body)
  mailer.set_subject(subject, mail_body)
  mailer.set_html_content(html_content, mail_body)
  mailer.set_plaintext_content(text_content, mail_body)
  mailer.set_reply_to(reply_to, mail_body)

  # Send the email 
  return mailer.send(mail_body)