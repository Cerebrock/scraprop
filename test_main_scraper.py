#!/usr/bin/env python3
"""
Test script for the main scraper with LLM integration - limited to 10 properties.
"""
import sys
import os
sys.path.append('src')

from scraprop import main

if __name__ == "__main__":
    print("🧪 Testing main scraper with LLM integration (max 10 properties)")
    print("=" * 70)
    
    # Run main scraper with property limit
    main(max_properties=10)
    
    print("\n" + "=" * 70)
    print("✅ Test completed! Check outputs/scraped_properties.csv for results") 