#!/usr/bin/env python3
"""
Webhook Setup Checker for Recall.ai Integration
"""

import requests
import os
import sys
from datetime import datetime

def check_server_status(base_url="http://localhost:8000"):
    """Check if the server is running"""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
            return True
        else:
            print(f"❌ Server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running?")
        return False
    except Exception as e:
        print(f"❌ Error checking server: {str(e)}")
        return False

def check_webhook_health(base_url="http://localhost:8000"):
    """Check webhook health endpoint"""
    try:
        response = requests.get(f"{base_url}/webhook/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("\n🔗 Webhook Health Check:")
            print(f"   Status: {data.get('status', 'unknown')}")
            print(f"   Webhook URL: {data.get('webhook_url', 'Not configured')}")
            print(f"   Webhook Secret: {data.get('webhook_secret', 'Not configured')}")
            print(f"   Recall API Token: {data.get('recall_api_token', 'Not configured')}")
            print(f"   Router Loaded: {data.get('router_loaded', False)}")
            print(f"   Endpoint Path: {data.get('endpoint_path', 'Unknown')}")
            
            return data.get('status') == 'healthy'
        else:
            print(f"❌ Webhook health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking webhook health: {str(e)}")
        return False

def check_environment_variables():
    """Check if required environment variables are set"""
    print("\n🔧 Environment Variables Check:")
    
    required_vars = {
        "RECALL_API_TOKEN": "Recall.ai API token",
        "RECALL_WEBHOOK_SECRET": "Webhook secret for verification",
        "RECALL_WEBHOOK_URL": "Public webhook URL",
        "GEMINI_API_KEY": "Gemini API key for summarization"
    }
    
    all_set = True
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: {'*' * len(value)} ({description})")
        else:
            print(f"   ❌ {var}: Not set ({description})")
            all_set = False
    
    return all_set

def test_webhook_endpoint(base_url="http://localhost:8000"):
    """Test the webhook endpoint with sample data"""
    try:
        response = requests.post(f"{base_url}/webhook/test", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"\n🧪 Webhook Test: {data.get('status', 'unknown')}")
            print(f"   Message: {data.get('message', 'No message')}")
            print(f"   Verification: {data.get('verification', 'Unknown')}")
            return data.get('status') == 'success'
        else:
            print(f"❌ Webhook test failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing webhook: {str(e)}")
        return False

def check_api_documentation(base_url="http://localhost:8000"):
    """Check if API documentation is accessible"""
    try:
        response = requests.get(f"{base_url}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ API documentation is accessible")
            print(f"   📖 Docs URL: {base_url}/docs")
            return True
        else:
            print(f"❌ API documentation not accessible: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking API docs: {str(e)}")
        return False

def main():
    """Main function to run all checks"""
    print("🚀 Recall.ai Webhook Setup Checker")
    print("=" * 50)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    base_url = "http://localhost:8000"
    
    # Check environment variables first
    env_ok = check_environment_variables()
    
    # Check server status
    server_ok = check_server_status(base_url)
    
    if not server_ok:
        print("\n❌ Server is not running. Please start the server first:")
        print("   cd backend")
        print("   python main.py")
        sys.exit(1)
    
    # Check webhook health
    webhook_ok = check_webhook_health(base_url)
    
    # Test webhook functionality
    test_ok = test_webhook_endpoint(base_url)
    
    # Check API documentation
    docs_ok = check_api_documentation(base_url)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Setup Summary:")
    print(f"   Environment Variables: {'✅' if env_ok else '❌'}")
    print(f"   Server Running: {'✅' if server_ok else '❌'}")
    print(f"   Webhook Health: {'✅' if webhook_ok else '❌'}")
    print(f"   Webhook Test: {'✅' if test_ok else '❌'}")
    print(f"   API Documentation: {'✅' if docs_ok else '❌'}")
    
    if all([env_ok, server_ok, webhook_ok, test_ok, docs_ok]):
        print("\n🎉 All checks passed! Your webhook is properly configured.")
        print("\n📝 Next steps:")
        print("   1. Ensure your webhook URL is publicly accessible")
        print("   2. Test with a real Recall.ai bot")
        print("   3. Check the logs for any issues")
    else:
        print("\n⚠️  Some checks failed. Please review the issues above.")
        print("\n🔧 Troubleshooting:")
        if not env_ok:
            print("   - Set all required environment variables in your .env file")
        if not webhook_ok:
            print("   - Check that the Recall.ai router is properly loaded")
        if not test_ok:
            print("   - Verify webhook secret configuration")
        print("   - Check server logs for detailed error messages")

if __name__ == "__main__":
    main() 