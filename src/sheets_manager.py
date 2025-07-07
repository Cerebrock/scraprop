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


class SheetsManager:
    """Manages Google Sheets integration for property data."""
    
    def __init__(self):
        """Initialize the Google Sheets manager."""
        self.gc = None
        self.sheet = None
        self.worksheet = None
        self.sheet_id = None
        
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
                print(f"✅ Created new Google Sheet: {self.sheet.title}")
                print(f"📋 Sheet ID: {self.sheet_id}")
                print(f"🔗 Sheet URL: https://docs.google.com/spreadsheets/d/{self.sheet_id}")
                print(f"💡 Add this to your .env file: GOOGLE_SHEET_ID={self.sheet_id}")
                
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
    
    def update_sheet(self, properties: List[Dict], clear_first: bool = False) -> bool:
        """
        Update the Google Sheet with property data.
        
        Args:
            properties: List of property dictionaries
            clear_first: Whether to clear the sheet before updating
            
        Returns:
            bool: True if update successful, False otherwise
        """
        if not self.worksheet:
            print("❌ Google Sheet not set up")
            return False
            
        if not properties:
            print("⚠️  No properties to update")
            return False
            
        try:
            # Convert to DataFrame for easier handling
            df = pd.DataFrame(properties)
            
            # Ensure all expected columns are present
            base_columns = ['url', 'price', 'expenses', 'neighbourhood', 'surface', 'rooms', 'upload_date', 'seen_date', 'description']
            llm_columns = [
                'score', 'score_breakdown', 
                'llm_neighbourhood', 'llm_is_ground_floor', 'llm_has_outdoor_space', 
                'llm_outdoor_space_type', 'llm_surface_m2', 'llm_price_numeric',
                'llm_near_important_avenue', 'llm_near_subway_train'
            ]
            all_columns = base_columns + llm_columns
            
            # Ensure all columns exist
            for col in all_columns:
                if col not in df.columns:
                    if col == 'score':
                        df[col] = 0
                    elif col == 'score_breakdown':
                        df[col] = ''
                    elif col in ['llm_is_ground_floor', 'llm_has_outdoor_space', 'llm_near_important_avenue', 'llm_near_subway_train']:
                        df[col] = False
                    elif col in ['llm_surface_m2', 'llm_price_numeric']:
                        df[col] = 0
                    else:
                        df[col] = ''
            
            # Process LLM analysis data
            if 'llm_analysis' in df.columns:
                for idx, row in df.iterrows():
                    llm_analysis = row.get('llm_analysis')
                    if llm_analysis and isinstance(llm_analysis, dict):
                        df.at[idx, 'llm_neighbourhood'] = llm_analysis.get('neighbourhood', '')
                        df.at[idx, 'llm_is_ground_floor'] = llm_analysis.get('is_ground_floor', False)
                        df.at[idx, 'llm_has_outdoor_space'] = llm_analysis.get('has_outdoor_space', False)
                        df.at[idx, 'llm_outdoor_space_type'] = llm_analysis.get('outdoor_space_type', 'none')
                        df.at[idx, 'llm_surface_m2'] = llm_analysis.get('surface_m2', 0)
                        df.at[idx, 'llm_price_numeric'] = llm_analysis.get('price_numeric', 0)
                        df.at[idx, 'llm_near_important_avenue'] = llm_analysis.get('near_important_avenue', False)
                        df.at[idx, 'llm_near_subway_train'] = llm_analysis.get('near_subway_train', False)
            
            # Convert score_breakdown dict to string
            if 'score_breakdown' in df.columns:
                for idx, row in df.iterrows():
                    score_breakdown = row.get('score_breakdown')
                    if score_breakdown and isinstance(score_breakdown, dict):
                        breakdown_str = '; '.join([f"{k}: {'+' if v >= 0 else ''}{v}" for k, v in score_breakdown.items()])
                        df.at[idx, 'score_breakdown'] = breakdown_str
            
            # Select and reorder columns
            df = df[all_columns]
            
            # Add timestamp column
            df.insert(0, 'last_updated', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            # Sort by score (highest first)
            df = df.sort_values('score', ascending=False)
            
            # Clear the sheet if requested
            if clear_first:
                self.worksheet.clear()
            
            # Convert DataFrame to list of lists for upload
            values = [df.columns.tolist()] + df.values.tolist()
            
            # Update the sheet
            if clear_first:
                self.worksheet.update('A1', values)
            else:
                # Check if we need to update existing data or append
                existing_data = self.worksheet.get_all_values()
                if len(existing_data) <= 1:  # Only headers or empty
                    self.worksheet.update('A1', values)
                else:
                    # For now, let's replace all data to keep it simple
                    self.worksheet.clear()
                    self.worksheet.update('A1', values)
            
            print(f"✅ Updated Google Sheet with {len(df)} properties")
            print(f"🔗 Sheet URL: https://docs.google.com/spreadsheets/d/{self.sheet_id}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to update Google Sheet: {e}")
            return False
    
    def get_sheet_url(self) -> Optional[str]:
        """Get the URL of the Google Sheet."""
        if self.sheet_id:
            return f"https://docs.google.com/spreadsheets/d/{self.sheet_id}"
        return None


def get_sheets_manager() -> Optional[SheetsManager]:
    """Get a SheetsManager instance if credentials are available."""
    manager = SheetsManager()
    if manager.authenticate() and manager.setup_sheet():
        return manager
    return None 