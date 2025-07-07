# Google Sheets Integration Setup

This guide will help you set up live Google Sheets integration for your property scraper.

## Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. In the project dashboard, click on "Enable APIs and Services"
4. Search for and enable these APIs:
   - **Google Sheets API**
   - **Google Drive API**

## Step 2: Create Service Account Credentials

1. In Google Cloud Console, go to **IAM & Admin** → **Service Accounts**
2. Click **"Create Service Account"**
3. Enter a name like "Property Scraper" and click **Create**
4. Skip the optional steps and click **Done**
5. Click on your newly created service account
6. Go to the **Keys** tab
7. Click **Add Key** → **Create New Key**
8. Choose **JSON** format and click **Create**
9. A JSON file will be downloaded - this contains your credentials

## Step 3: Configure Environment Variables

Add these variables to your `.env` file:

### Option A: Using JSON File (Recommended for local development)
```bash
# Place the downloaded JSON file in your project directory as 'credentials.json'
GOOGLE_SHEETS_CREDENTIALS_FILE=credentials.json

# Optional: Your email to automatically share the sheet with you
GOOGLE_SHEETS_SHARE_EMAIL=your-email@gmail.com

# Optional: If you want to use an existing sheet, add its ID
# GOOGLE_SHEET_ID=your_existing_sheet_id_here
```

### Option B: Using JSON String (Recommended for production/cron)
```bash
# Copy the entire contents of the JSON file as a string
GOOGLE_SHEETS_CREDENTIALS={"type":"service_account","project_id":"your-project",...}

# Optional: Your email to automatically share the sheet with you
GOOGLE_SHEETS_SHARE_EMAIL=your-email@gmail.com

# Optional: If you want to use an existing sheet, add its ID
# GOOGLE_SHEET_ID=your_existing_sheet_id_here
```

## Step 4: Install Dependencies

Update your dependencies:

```bash
pip install -r requirements.txt
```

## Step 5: Test the Integration

Run a test to verify everything is working:

```bash
cd src
python -c "
import sys
sys.path.append('.')
from sheets_manager import get_sheets_manager

print('Testing Google Sheets integration...')
manager = get_sheets_manager()
if manager:
    print('✅ Google Sheets integration working!')
    print(f'🔗 Sheet URL: {manager.get_sheet_url()}')
else:
    print('❌ Google Sheets integration failed')
"
```

## Step 6: Run Your Scraper

Now when you run your scraper, it will automatically update both the CSV file and the Google Sheet:

```bash
python src/scraprop.py
```

## How It Works

1. **CSV First**: The scraper continues to save data to `outputs/scraped_properties.csv`
2. **Google Sheets Update**: After saving the CSV, it automatically updates your Google Sheet
3. **Live Data**: The Google Sheet is sorted by score (highest first) and includes a timestamp
4. **Real-time Access**: You can view, share, and analyze the data in real-time through Google Sheets

## Features

- ✅ **Automatic Updates**: Every scraper run updates the Google Sheet
- ✅ **Sorted by Score**: Properties are automatically sorted by LLM score (highest first)
- ✅ **Timestamps**: Each update includes a timestamp
- ✅ **All Data**: Includes all scraped data plus LLM analysis
- ✅ **Shareable**: Easy to share with others or access from mobile
- ✅ **Backup**: CSV files are still created as backup

## Troubleshooting

### "Authentication failed"
- Check that your JSON credentials file is valid
- Ensure the Google Sheets API and Google Drive API are enabled
- Verify the service account has the correct permissions

### "Could not open sheet"
- If using an existing sheet ID, make sure the service account has access to it
- Try removing `GOOGLE_SHEET_ID` from `.env` to create a new sheet

### "Permission denied"
- The service account needs access to create/edit sheets
- Make sure you've enabled both Google Sheets API and Google Drive API

### Sheet not updating
- Check the console output for error messages
- Verify your internet connection
- Ensure the Google APIs are not rate-limited

## Sheet Structure

Your Google Sheet will contain these columns:

| Column | Description |
|--------|-------------|
| last_updated | Timestamp of last update |
| url | Property URL |
| price | Listed price |
| expenses | Monthly expenses |
| neighbourhood | Property location |
| surface | Property size |
| rooms | Number of rooms |
| upload_date | When property was posted |
| seen_date | When we first saw it |
| description | Property description |
| score | LLM analysis score |
| score_breakdown | Detailed scoring |
| llm_* | Various LLM analysis fields |

The sheet is automatically sorted by `score` (highest first) so the best properties appear at the top! 