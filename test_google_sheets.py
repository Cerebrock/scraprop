#!/usr/bin/env python3
"""
Test script for Google Sheets integration.
Run this to verify your Google Sheets setup is working.
"""
import sys
import os
sys.path.append('src')

from sheets_manager import get_sheets_manager
from datetime import datetime


def test_google_sheets():
    """Test Google Sheets integration with sample data."""
    print("🧪 Testing Google Sheets Integration")
    print("=" * 50)
    
    # Test authentication
    print("1. Testing authentication...")
    manager = get_sheets_manager()
    
    if not manager:
        print("❌ Google Sheets authentication failed")
        print("\n📋 To fix this:")
        print("   1. Follow the setup guide in setup_google_sheets.md")
        print("   2. Make sure you have credentials.json or GOOGLE_SHEETS_CREDENTIALS in .env")
        print("   3. Ensure Google Sheets API and Drive API are enabled")
        return False
    
    print("✅ Authentication successful!")
    
    # Test with sample data
    print("\n2. Testing sheet update with sample data...")
    
    sample_properties = [
        {
            'url': 'https://example.com/property1',
            'price': '$500.000',
            'expenses': '$30.000',
            'neighbourhood': 'Belgrano',
            'surface': '80 m²',
            'rooms': '3',
            'upload_date': 'Hace 2 días',
            'seen_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'description': 'Beautiful apartment with terrace in Belgrano',
            'score': 23,
            'score_breakdown': {
                'Location (Belgrano)': 10,
                'Ground Floor': 10,
                'Outdoor Space': 3
            },
            'llm_analysis': {
                'neighbourhood': 'Belgrano',
                'is_ground_floor': True,
                'has_outdoor_space': True,
                'outdoor_space_type': 'terraza',
                'surface_m2': 80,
                'price_numeric': 500000,
                'near_important_avenue': False,
                'near_subway_train': False
            }
        },
        {
            'url': 'https://example.com/property2',
            'price': '$700.000',
            'expenses': '$45.000',
            'neighbourhood': 'Palermo',
            'surface': '60 m²',
            'rooms': '2',
            'upload_date': 'Hace 1 día',
            'seen_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'description': 'Modern apartment in Palermo',
            'score': 15,
            'score_breakdown': {
                'Surface (60m²)': 5,
                'Near Important Avenue': 5,
                'Near Subway/Train': 4,
                'Price ($700,000)': 1
            },
            'llm_analysis': {
                'neighbourhood': 'Palermo',
                'is_ground_floor': False,
                'has_outdoor_space': False,
                'outdoor_space_type': 'none',
                'surface_m2': 60,
                'price_numeric': 700000,
                'near_important_avenue': True,
                'near_subway_train': True
            }
        },
        {
            'url': 'https://example.com/property3',
            'price': '$400.000',
            'expenses': '$20.000',
            'neighbourhood': 'San Nicolas',
            'surface': '45 m²',
            'rooms': '1',
            'upload_date': 'Hace 3 días',
            'seen_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'description': 'local comercial en alquiler',
            'score': 0,
            'score_breakdown': {
                'Commercial Property (Local)': -15,
                'Price ($400,000)': 12,
                'Surface (45m²)': 3
            },
            'llm_analysis': {
                'neighbourhood': 'San Nicolas',
                'is_ground_floor': True,
                'has_outdoor_space': False,
                'outdoor_space_type': 'none',
                'surface_m2': 45,
                'price_numeric': 400000,
                'near_important_avenue': False,
                'near_subway_train': False
            }
        }
    ]
    
    # Update the sheet
    success = manager.update_sheet(sample_properties, clear_first=True)
    
    if success:
        print("✅ Sheet update successful!")
        sheet_url = manager.get_sheet_url()
        print(f"\n🔗 View your test data: {sheet_url}")
        print("\n📊 Test data includes:")
        print("   • High-scoring property (Belgrano, score: 23)")
        print("   • Medium-scoring property (Palermo, score: 15)")
        print("   • Penalized commercial property (score: 0)")
        print("\n✨ The sheet should be sorted by score (highest first)")
        return True
    else:
        print("❌ Sheet update failed")
        return False


def main():
    """Main test function."""
    print(f"🏠 Property Scraper - Google Sheets Test")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check environment
    print("🔍 Checking environment...")
    has_creds_file = os.path.exists('credentials.json')
    has_creds_env = bool(os.getenv('GOOGLE_SHEETS_CREDENTIALS'))
    has_creds_file_env = bool(os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE'))
    
    print(f"   credentials.json file: {'✅' if has_creds_file else '❌'}")
    print(f"   GOOGLE_SHEETS_CREDENTIALS env var: {'✅' if has_creds_env else '❌'}")
    print(f"   GOOGLE_SHEETS_CREDENTIALS_FILE env var: {'✅' if has_creds_file_env else '❌'}")
    
    if not (has_creds_file or has_creds_env or has_creds_file_env):
        print("\n❌ No Google Sheets credentials found!")
        print("📋 Please follow the setup guide in setup_google_sheets.md")
        return
    
    print()
    
    # Run the test
    success = test_google_sheets()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Google Sheets integration is working perfectly!")
        print("💡 Your scraper will now automatically update Google Sheets")
        print("🚀 Run 'python src/scraprop.py' to start scraping with live updates")
    else:
        print("❌ Google Sheets integration test failed")
        print("📖 Check the setup guide in setup_google_sheets.md")
        print("🔧 Common issues:")
        print("   • API not enabled (Google Sheets API + Drive API)")
        print("   • Invalid credentials file")
        print("   • Service account permissions")


if __name__ == "__main__":
    main() 