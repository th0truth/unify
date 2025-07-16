from typing import Dict, Any
from pathlib import Path
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

def render_email_template(*, template_name: str, context: Dict[str, Any]) -> str:
  template_path = (
    Path(__file__).parent / "templates" / "email" / template_name
  ).read_text()
  html_content = Template(template_path).render(context)
  return html_content

def send_email(to: str, subject: str, html_content: str, text_content: str, reply_to_name: str, reply_to_email: str) -> str:
  # Define an empty dict to populate with mail values
  mail_body = {}

  # Set sender details
  mail_from = {
    "name": settings.MAILERSEND_SMTP_NAME,
    "email": settings.MAILERSEND_SMTP_USERNAME
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
      "email": reply_to_email,
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