#!/usr/bin/env python3
"""
Test script for running live tests on all three websites with the new scoring system.
"""
import os
import sys
from dotenv import load_dotenv

# Add src directory to path
sys.path.append('src')

from utils import get_html
from scraper import extract_ads, extract_property_details
from llm_scorer import get_scorer

def test_real_websites():
    """
    Test the LLM scorer with real data from all three websites.
    """
    
    # Load environment variables
    load_dotenv()
    
    # Initialize LLM scorer
    scorer = get_scorer()
    if not scorer:
        print("❌ LLM Scorer not available (check GEMINI_API_KEY)")
        return False
    
    print("✅ LLM Scorer initialized successfully")
    
    # Define the actual URLs from urls_to_scrap.txt
    test_urls = {
        "Zonaprop": "https://www.zonaprop.com.ar/casas-ph-locales-comerciales-alquiler-capital-federal-vicente-lopez-florida-mas-50-m2-400000-1000000-pesos.html",
        "Argenprop": "https://www.argenprop.com/departamento-y-ph-alquiler-localidad-florida-y-vicente-lopez-y-olivos-y-la-lucila-y-martinez-y-san-isidro-y-beccar-y-victoria-y-san-fernando-y-tigre-y-nordelta-mas-de-50-m2-y-publicado-hace-menos-de-1-mes",
        "MercadoLibre": "https://inmuebles.mercadolibre.com.ar/ph/alquiler/bsas-gba-norte/vicente-lopez/_PriceRange_400000ARS-1000000ARS_NoIndex_True_TOTAL*AREA_60-*"
    }
    
    print("\n🧪 Testing LLM scoring with real data from all three websites...")
    print("=" * 70)
    
    for site, url in test_urls.items():
        print(f"\n🌐 SITE: {site}")
        print("-" * 50)
        
        try:
            # 1. Scrape the search results page
            print(f"1. Scraping search page...")
            
            # Use Playwright for Zonaprop, default for others
            strategy = 'playwright' if 'zonaprop' in site.lower() else 'default'
            html_content = get_html(url, strategy=strategy)

            if not html_content:
                print(f"   ❌ FAILED to get search results")
                continue

            ads = extract_ads(url, html_content)
            
            if not ads:
                print("   ❌ No ads found on the search page. Skipping site.")
                continue

            print(f"   ✅ Found {len(ads)} ads. Testing the first one.")
            
            # 2. Extract details for the first ad
            first_ad_url = ads[0]['url']
            print(f"2. Extracting details for: {first_ad_url[:60]}...")
            ad_html = get_html(first_ad_url) # Use default strategy
                
            if not ad_html:
                print(f"   ❌ FAILED to get ad page")
                continue

            property_details = extract_property_details(first_ad_url, ad_html)
            
            if not property_details:
                print("   ❌ Failed to extract property details.")
                continue

            print("   ✅ Details extracted successfully.")
            
            # 3. Analyze with LLM and score
            print("3. 🤖 Analyzing with LLM...")
            analyzed_property = scorer.analyze_property(property_details)
            
            score = analyzed_property.get('score', 0)
            score_breakdown = analyzed_property.get('score_breakdown', {})
            llm_analysis = analyzed_property.get('llm_analysis', {})
            
            print("   ✅ Analysis complete.")
            
            # 4. Display results
            print(f"\n==================== REPORT: {site} ====================")
            print(f"⭐ SCORE: {score}")
            
            if score_breakdown:
                print("\n📊 Score Breakdown:")
                for reason, points in score_breakdown.items():
                    print(f"   • {reason}: +{points}")
            
            if llm_analysis:
                print(f"\n🏠 Property Analysis:")
                print(f"   📍 Neighborhood: {llm_analysis.get('neighbourhood', 'N/A')}")
                print(f"   🌳 Ground Floor: {llm_analysis.get('is_ground_floor', 'N/A')}")
                print(f"   🌿 Outdoor Space: {llm_analysis.get('has_outdoor_space', 'N/A')}")
                if llm_analysis.get('outdoor_space_type', 'none') != 'none':
                    print(f"   🌸 Outdoor Type: {llm_analysis.get('outdoor_space_type')}")
                print(f"   📏 Surface: {llm_analysis.get('surface_m2', 'N/A')}m²")
                print(f"   💰 Price: ${llm_analysis.get('price_numeric', 'N/A'):,}")
            
            # Display basic property info
            print(f"\n📋 Basic Info:")
            print(f"   🔗 URL: {property_details.get('url', 'N/A')}")
            print(f"   💵 Listed Price: {property_details.get('price', 'N/A')}")
            print(f"   📐 Listed Surface: {property_details.get('surface', 'N/A')}")
            print(f"   🏘️ Listed Area: {property_details.get('neighbourhood', 'N/A')}")
            
            print("=" * 60)
            
        except Exception as e:
            print(f"   ❌ An error occurred during the test for {site}: {e}")
            
    print("\n✅ Live test run finished!")

if __name__ == "__main__":
    test_real_websites() 