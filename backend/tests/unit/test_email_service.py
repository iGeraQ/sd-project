import pytest
from app.services.email_service import EmailService

@pytest.mark.asyncio
async def test_send_email_renders_and_calls_resend(mock_resend):
    """Test that the email service correctly renders the template and calls the Resend API."""
    context = {
        "full_name": "Test User",
        "frontend_url": "http://localhost:3000"
    }
    
    result = await EmailService.send_email(
        to_email="test@example.com",
        subject="Welcome",
        template_name="welcome.html",
        context=context
    )
    
    # Assert email was "sent"
    assert result is True
    
    # Assert mock was called exactly once
    mock_resend.assert_called_once()
    
    # Verify the arguments passed to Resend API
    call_args = mock_resend.call_args[0][0]
    assert call_args["to"] == ["test@example.com"]
    assert call_args["subject"] == "Welcome"
    assert "Test User" in call_args["html"]
    assert "http://localhost:3000/login" in call_args["html"]

@pytest.mark.asyncio
async def test_send_email_invalid_template(mock_resend):
    """Test that sending fails gracefully if the template does not exist."""
    result = await EmailService.send_email(
        to_email="test@example.com",
        subject="Welcome",
        template_name="non_existent.html",
        context={}
    )
    
    assert result is False
    mock_resend.assert_not_called()
