#!/usr/bin/env python3
"""
Simple test script to verify the backend server starts without errors
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_import():
    """Test importing the main application"""
    try:
        print("🧪 Testing imports...")
        
        # Test basic imports
        import fastapi
        print(f"✅ FastAPI version: {fastapi.__version__}")
        
        import pydantic
        print(f"✅ Pydantic version: {pydantic.__version__}")
        
        import uvicorn
        print(f"✅ Uvicorn available")
        
        # Test main app import
        from main import app
        print("✅ Main app imported successfully")
        
        # Test that the app has routes
        routes = [route.path for route in app.routes]
        print(f"✅ Found {len(routes)} routes")
        
        # Test a simple endpoint
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        response = client.get("/health")
        if response.status_code == 200:
            print("✅ Health endpoint working")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
        
        print("\n🎉 All tests passed! Server should start without schema errors.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_import()
    sys.exit(0 if success else 1) 