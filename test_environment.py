#!/usr/bin/env python3
"""
Simple test script to verify environment variables and email functionality
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_environment():
    """Test if environment variables are set correctly"""
    print("🔍 ENVIRONMENT VARIABLE TEST")
    print("=" * 50)
    
    # Check environment variables
    email_api_key = os.getenv('EMAIL_API_KEY')
    notification_email = os.getenv('NOTIFICATION_EMAIL')
    
    print(f"📧 EMAIL_API_KEY present: {'Yes' if email_api_key else 'No'}")
    if email_api_key:
        print(f"📧 EMAIL_API_KEY (first 20 chars): {email_api_key[:20]}...")
        print(f"📧 EMAIL_API_KEY (last 10 chars): ...{email_api_key[-10:]}")
    
    print(f"📧 NOTIFICATION_EMAIL: {notification_email}")
    
    # Check if .env file exists
    env_file_exists = os.path.exists('.env')
    print(f"📁 .env file exists: {env_file_exists}")
    
    if env_file_exists:
        print("📄 .env file contents:")
        try:
            with open('.env', 'r') as f:
                content = f.read()
            for line in content.split('\n'):
                if line.strip() and not line.startswith('#'):
                    key = line.split('=')[0]
                    value = line.split('=', 1)[1] if '=' in line else ''
                    if 'API_KEY' in key:
                        print(f"  {key}={value[:20]}...{value[-10:] if len(value) > 30 else value}")
                    else:
                        print(f"  {key}={value}")
        except Exception as e:
            print(f"  Error reading .env: {e}")
    
    # Test sib-api-v3-sdk import
    try:
        import sib_api_v3_sdk
        print("✅ sib-api-v3-sdk imported successfully")
        
        if email_api_key:
            # Test API connection
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key['api-key'] = email_api_key
            api_instance = sib_api_v3_sdk.AccountApi(sib_api_v3_sdk.ApiClient(configuration))
            
            try:
                account_info = api_instance.get_account()
                print(f"✅ Brevo API connection successful")
                print(f"📧 Account email: {account_info.email}")
                print(f"📊 Plan: {account_info.plan[0].type}")
                print(f"📈 Credits remaining: {account_info.plan[0].credits}")
            except Exception as api_error:
                print(f"❌ Brevo API connection failed: {api_error}")
        else:
            print("⚠ Cannot test API connection - no API key")
            
    except ImportError as e:
        print(f"❌ sib-api-v3-sdk import failed: {e}")
    
    print("=" * 50)
    
    # Return summary
    return {
        'email_api_key_present': bool(email_api_key),
        'notification_email_present': bool(notification_email),
        'env_file_exists': env_file_exists,
        'api_key_value': email_api_key[:20] + '...' if email_api_key else None,
        'notification_email_value': notification_email
    }

if __name__ == "__main__":
    print("🧪 EVCS Scraper Environment Test")
    print("=" * 60)
    
    result = test_environment()
    
    print("\n📋 SUMMARY:")
    print("=" * 30)
    for key, value in result.items():
        status = "✅" if value else "❌"
        print(f"{status} {key}: {value}")
    
    if result['email_api_key_present'] and result['notification_email_present']:
        print("\n🎯 Environment looks good! Email notifications should work.")
    else:
        print("\n⚠ Issues detected. Check GitHub secrets configuration.")
