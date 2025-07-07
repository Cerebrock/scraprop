"""
Google Sheets Manager: Handles uploading property data to Google Sheets
"""
import os
import json
import pandas as pd
from typing import List, Dict, Optional
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class SheetsManager:
    """Manages Google Sheets integration for property data."""
    
    def __init__(self):
        """Initialize the Google Sheets manager."""
        self.gc = None
        self.sheet = None
        self.worksheet = None
        self.sheet_id = None
        self.header_written = False
        
        # Define the desired column order
        self.columns = [
            'last_updated', 'score', 'llm_price_numeric', 'llm_surface_m2',
            'llm_is_ground_floor', 'llm_has_outdoor_space', 'llm_near_important_avenue', 'llm_near_subway_train',
            'url', 'llm_neighbourhood', 'llm_outdoor_space_type',
            'price', 'surface', 'neighbourhood', 'rooms', 'expenses', 'description',
            'score_breakdown', 'upload_date', 'seen_date'
        ]
        
    def authenticate(self) -> bool:
        """
        Authenticate with Google Sheets API using service account credentials.
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            # Try to get credentials from environment variable (JSON string)
            creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
            if creds_json:
                creds_dict = json.loads(creds_json)
                credentials = Credentials.from_service_account_info(
                    creds_dict,
                    scopes=[
                        'https://www.googleapis.com/auth/spreadsheets',
                        'https://www.googleapis.com/auth/drive'
                    ]
                )
            else:
                # Try to load from file
                creds_file = os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE', 'credentials.json')
                if not os.path.exists(creds_file):
                    print(f"⚠️  Google Sheets credentials not found. Please set GOOGLE_SHEETS_CREDENTIALS or place credentials.json file.")
                    return False
                
                credentials = Credentials.from_service_account_file(
                    creds_file,
                    scopes=[
                        'https://www.googleapis.com/auth/spreadsheets',
                        'https://www.googleapis.com/auth/drive'
                    ]
                )
            
            self.gc = gspread.authorize(credentials)
            print("✅ Google Sheets authentication successful")
            return True
            
        except Exception as e:
            print(f"❌ Google Sheets authentication failed: {e}")
            return False
    
    def setup_sheet(self, sheet_name: str = "Property Scraper Data") -> bool:
        """
        Create or open the Google Sheet for property data.
        
        Args:
            sheet_name: Name of the Google Sheet
            
        Returns:
            bool: True if setup successful, False otherwise
        """
        if not self.gc:
            print("❌ Not authenticated with Google Sheets")
            return False
            
        try:
            # Try to get existing sheet ID from environment
            self.sheet_id = os.getenv('GOOGLE_SHEET_ID')
            
            if self.sheet_id:
                # Open existing sheet by ID
                try:
                    self.sheet = self.gc.open_by_key(self.sheet_id)
                    print(f"✅ Opened existing Google Sheet: {self.sheet.title}")
                except Exception as e:
                    print(f"⚠️  Could not open sheet with ID {self.sheet_id}: {e}")
                    self.sheet_id = None
            
            if not self.sheet_id:
                # Create new sheet
                self.sheet = self.gc.create(sheet_name)
                self.sheet_id = self.sheet.id
                print()
                print("🎉" + "="*60)
                print("🎉 NEW GOOGLE SHEET CREATED!")
                print("🎉" + "="*60)
                print(f"📋 Sheet Name: {self.sheet.title}")
                print(f"🔗 Sheet URL: https://docs.google.com/spreadsheets/d/{self.sheet_id}")
                print(f"💡 Add this to your .env file: GOOGLE_SHEET_ID={self.sheet_id}")
                print("🎉" + "="*60)
                print()
                
                # Share with your email if specified
                share_email = os.getenv('GOOGLE_SHEETS_SHARE_EMAIL')
                if share_email:
                    try:
                        self.sheet.share(share_email, perm_type='user', role='writer')
                        print(f"📧 Shared sheet with: {share_email}")
                    except Exception as e:
                        print(f"⚠️  Could not share sheet: {e}")
            
            # Get the first worksheet
            self.worksheet = self.sheet.sheet1
            return True
            
        except Exception as e:
            print(f"❌ Failed to setup Google Sheet: {e}")
            return False
    
    def _ensure_header(self):
        """Ensure the sheet has a header row. If not, write it."""
        if self.header_written:
            return
            
        try:
            # Check only the first cell to avoid fetching the whole sheet
            header_exists = self.worksheet.acell('A1').value is not None
            if not header_exists:
                print("📝 Writing header row to new sheet...")
                self.worksheet.update('A1', [self.columns])
            self.header_written = True
        except Exception as e:
            print(f"⚠️  Could not ensure header: {e}")
            # Assume it's okay and continue
            self.header_written = True
            
    def append_property(self, property_details: Dict) -> bool:
        """
        Append a single property to the Google Sheet, adapting to the current column order.
        
        Args:
            property_details: Dictionary of the property to append
            
        Returns:
            bool: True if append was successful, False otherwise
        """
        if not self.worksheet:
            print("❌ Google Sheet not set up")
            return False

        try:
            # 1. Ensure a header row exists
            self._ensure_header()

            # 2. Fetch the current header to get the column order
            header = self.worksheet.row_values(1)
            if not header:
                print("❌ Cannot append: Sheet header is empty.")
                return False

            # 3. Flatten the property data into a single dictionary
            flat_property = self._flatten_property(property_details)

            # 4. Build the row in the correct order
            row_to_append = [flat_property.get(col, '') for col in header]

            # 5. Append the new row to the sheet
            self.worksheet.append_row(row_to_append, value_input_option='USER_ENTERED')
            return True

        except Exception as e:
            print(f"❌ Failed to append property to Google Sheet: {e}")
            return False

    def _flatten_property(self, property_details: Dict) -> Dict:
        """Flatten the nested property dictionary into a single level."""
        flat_data = {}

        # Copy top-level keys
        for key, value in property_details.items():
            if key not in ['llm_analysis', 'score_breakdown']:
                flat_data[key] = value

        # Flatten llm_analysis
        llm_analysis = property_details.get('llm_analysis', {})
        if llm_analysis and isinstance(llm_analysis, dict):
            flat_data['llm_neighbourhood'] = llm_analysis.get('neighbourhood', '')
            flat_data['llm_is_ground_floor'] = llm_analysis.get('is_ground_floor', False)
            flat_data['llm_has_outdoor_space'] = llm_analysis.get('has_outdoor_space', False)
            flat_data['llm_outdoor_space_type'] = llm_analysis.get('outdoor_space_type', 'none')
            flat_data['llm_surface_m2'] = llm_analysis.get('surface_m2', 0)
            flat_data['llm_price_numeric'] = llm_analysis.get('price_numeric', 0)
            flat_data['llm_near_important_avenue'] = llm_analysis.get('near_important_avenue', False)
            flat_data['llm_near_subway_train'] = llm_analysis.get('near_subway_train', False)

        # Convert score_breakdown dict to string
        score_breakdown = property_details.get('score_breakdown', {})
        if score_breakdown and isinstance(score_breakdown, dict):
            breakdown_str = '; '.join([f"{k}: {'+' if v >= 0 else ''}{v}" for k, v in score_breakdown.items()])
            flat_data['score_breakdown'] = breakdown_str
        else:
             flat_data['score_breakdown'] = ''

        # Add timestamp
        flat_data['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        return flat_data

    def get_sheet_url(self) -> Optional[str]:
        """Get the URL of the Google Sheet."""
        if self.sheet_id:
            return f"https://docs.google.com/spreadsheets/d/{self.sheet_id}"
        return None
        
    def get_seen_urls(self) -> List[str]:
        """Get all previously seen URLs from the 'url' column in the sheet."""
        if not self.worksheet:
            return []
        
        try:
            print("Fetching seen URLs from Google Sheet...")
            header = self.worksheet.row_values(1)
            if 'url' not in header:
                print("⚠️  'url' column not found in sheet header. Cannot fetch seen URLs.")
                return []
            
            url_col_index = header.index('url') + 1  # gspread is 1-indexed
            urls = self.worksheet.col_values(url_col_index)[1:] # Skip header
            print(f"Found {len(urls)} seen URLs in the sheet.")
            return urls
        except Exception as e:
            print(f"⚠️  Could not get seen URLs from sheet: {e}")
            return []

def get_sheets_manager() -> Optional[SheetsManager]:
    """Factory function to get a configured SheetsManager instance."""
    manager = SheetsManager()
    if manager.authenticate():
        if manager.setup_sheet():
            return manager
    return None 