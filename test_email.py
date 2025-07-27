#!/usr/bin/env python3
"""
Test script for email notifications
Run this to test email functionality before deploying to GitHub Actions
"""

import os
import tempfile
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_email_notification():
    """Test the email notification functionality"""
    try:
        import sib_api_v3_sdk
        from sib_api_v3_sdk.rest import ApiException
    except ImportError:
        print("❌ sib-api-v3-sdk not installed. Run: pip install sib-api-v3-sdk")
        return False

    email_api_key = os.getenv('EMAIL_API_KEY')
    notification_email = os.getenv('NOTIFICATION_EMAIL')
    
    if not email_api_key:
        print("❌ EMAIL_API_KEY not found in .env file")
        return False
        
    if not notification_email:
        print("❌ NOTIFICATION_EMAIL not found in .env file")
        return False
    
    print(f"📧 Testing email to: {notification_email}")
    
    try:
        # Configure SendinBlue API
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = email_api_key
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
        
        # Create a test file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("This is a test attachment from the EVCS scraper.")
            test_file_path = f.name
        
        # Read the test file for attachment
        with open(test_file_path, 'rb') as f:
            file_content = f.read()
        
        # Prepare test email
        subject = "🧪 EVCS Scraper Email Test"
        html_content = """
        <html>
        <body>
            <h2>📧 Email Test Successful!</h2>
            <p>This is a test email from the EVCS Data Scraper.</p>
            <p>If you're receiving this, email notifications are working correctly.</p>
            <p><strong>Test details:</strong></p>
            <ul>
                <li>SendinBlue API: ✅ Connected</li>
                <li>Email delivery: ✅ Working</li>
                <li>File attachments: ✅ Supported</li>
            </ul>
            <p>You can now safely deploy the scraper to GitHub Actions.</p>
            <hr>
            <p><em>This is a test message from the EVCS Data Scraper.</em></p>
        </body>
        </html>
        """
        
        # Prepare attachment
        attachment = [{
            "content": file_content,
            "name": "test_attachment.txt"
        }]
        
        # Send test email
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": notification_email}],
            subject=subject,
            html_content=html_content,
            sender={"name": "EVCS Scraper", "email": "jimbarcos01@gmail.com"},
            attachment=attachment
        )
        
        api_response = api_instance.send_transac_email(send_smtp_email)
        print(f"✅ Test email sent successfully!")
        print(f"📨 Message ID: {api_response.message_id}")
        print(f"📬 Check your inbox at: {notification_email}")
        
        # Clean up test file
        os.unlink(test_file_path)
        
        return True
        
    except ApiException as e:
        print(f"❌ SendinBlue API error: {e}")
        return False
    except Exception as e:
        print(f"❌ Email test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing EVCS Scraper Email Notifications")
    print("-" * 50)
    
    success = test_email_notification()
    
    print("-" * 50)
    if success:
        print("✅ Email test completed successfully!")
        print("🚀 You can now deploy to GitHub Actions.")
    else:
        print("❌ Email test failed!")
        print("🔧 Please check your configuration and try again.")
    
    print("\n📋 Next steps:")
    print("1. Add EMAIL_API_KEY and NOTIFICATION_EMAIL to GitHub Secrets")
    print("2. Commit and push your changes to trigger the workflow")
    print("3. Monitor the Actions tab for execution status")
