"""
Quick import contacts from the user's Google Sheets base.
This script directly imports contacts from the shared spreadsheet.
"""

import sys
from pathlib import Path

# Add parent directory to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from core import db

# The user's spreadsheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ndEkxU5g12iz5cLDuDyDUoT6cgoWAi9-/edit?gid=1234938014#gid=1234938014"


def import_contacts():
    """Import contacts from the user's base."""
    
    # Initialize database
    db.init_db()
    
    print("📥 Importing contacts from Google Sheets...")
    print(f"URL: {SHEET_URL}")
    print()
    
    # Check for credentials
    credentials_path = ROOT / "credentials.json"
    if not credentials_path.exists():
        print("❌ Error: credentials.json not found!")
        print()
        print("To use Google Sheets import, you need to:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project")
        print("3. Enable Google Sheets API")
        print("4. Create a service account")
        print("5. Download the JSON key file")
        print("6. Save it as 'credentials.json' in this folder:")
        print(f"   {ROOT}")
        print("7. Share your Google Sheet with the service account email")
        print()
        print("Alternatively, you can import contacts manually via the bot.")
        return
    
    # Authenticate
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    try:
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            str(credentials_path), scope
        )
        gc = gspread.authorize(credentials)
        
        # Extract sheet ID
        sheet_id = SHEET_URL.split('/d/')[1].split('/')[0]
        
        # Open the sheet
        sheet = gc.open_by_key(sheet_id)
        worksheet = sheet.sheet1
        
        # Get all records
        records = worksheet.get_all_records()
        
        if not records:
            print("⚠️ No data found in the sheet")
            return
        
        print(f"📊 Found {len(records)} rows in the sheet")
        print()
        
        # Parse contacts
        contacts = []
        for row in records:
            username = str(row.get('SSYLKA', '')).strip()
            name = str(row.get('NAME', '')).strip()
            description = str(row.get('OPISANIYE', '')).strip()
            
            if username:
                # Clean username
                if username.startswith('@'):
                    username = username[1:]
                if 't.me/' in username:
                    username = username.split('t.me/')[-1]
                
                contacts.append({
                    'username': username,
                    'name': name,
                    'description': description
                })
        
        print(f"✅ Parsed {len(contacts)} valid contacts")
        print()
        
        # Import to database
        count = db.import_contacts_from_list(contacts, group_name="hr_recruiters")
        
        print(f"🎉 Successfully imported {count} contacts to database!")
        print(f"   Group: hr_recruiters")
        print()
        print("You can now use these contacts in the bot.")
        print("Start the bot with: start.bat")
        
    except gspread.exceptions.SpreadsheetNotFound:
        print("❌ Error: Spreadsheet not found!")
        print()
        print("Make sure you:")
        print("1. Shared the sheet with the service account email")
        print("2. Set sharing permissions to 'Anyone with the link can view'")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == '__main__':
    import_contacts()
