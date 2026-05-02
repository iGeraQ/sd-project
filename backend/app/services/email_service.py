"""Email service — manages email sending using Resend and Jinja2 templates."""

import os
import resend
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings

# Initialize Resend
resend.api_key = settings.resend_api_key

# Initialize Jinja2 Environment
# Look for templates in the app/templates directory
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(['html', 'xml'])
)


class EmailService:
    """Service to render templates and send emails asynchronously."""

    @staticmethod
    async def send_email(to_email: str, subject: str, template_name: str, context: dict) -> bool:
        """
        Render a Jinja2 template and send it via Resend.
        In a real production app, this should ideally be dispatched to a background worker (e.g. Celery or FastAPI BackgroundTasks).
        """
        # Render HTML template
        try:
            template = env.get_template(f"email/{template_name}")
            html_content = template.render(**context)
        except Exception as e:
            print(f"Error rendering template {template_name}: {e}")
            return False

        # Send email via Resend
        try:
            # Resend's Python SDK currently sends synchronously under the hood,
            # but we define this as async for future compatibility or to run in executor.
            params = {
                "from": settings.from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_content
            }
            email = resend.Emails.send(params)
            print(f"Email sent successfully. ID: {email.get('id')}")
            return True
        except Exception as e:
            print(f"Failed to send email to {to_email}: {e}")
            return False
