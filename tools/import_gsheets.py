"""
Import contacts from Google Sheets.
Usage: python tools/import_gsheets.py <sheet_url> [--group <group_name>]

Requirements:
- Google Sheets API credentials (service account JSON)
- Share the sheet with the service account email

Setup:
1. Go to https://console.cloud.google.com/
2. Create a project
3. Enable Google Sheets API
4. Create a service account
5. Download the JSON key file
6. Save it as 'credentials.json' in the project root
7. Share your Google Sheet with the service account email
"""

import sys
import os
import argparse
from pathlib import Path

# Add parent directory to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from core import db


def import_from_google_sheets(sheet_url: str, group_name: str = "imported") -> int:
    """Import contacts from Google Sheets."""
    
    # Check for credentials
    credentials_path = ROOT / "credentials.json"
    if not credentials_path.exists():
        print("❌ Error: credentials.json not found!")
        print("\nTo use Google Sheets import:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project and enable Google Sheets API")
        print("3. Create a service account and download the JSON key")
        print("4. Save it as 'credentials.json' in the project root")
        print("5. Share your Google Sheet with the service account email")
        return 0
    
    # Authenticate
    scope = [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ]
    
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        str(credentials_path), scope
    )
    gc = gspread.authorize(credentials)
    
    # Extract sheet ID from URL
    if '/d/' in sheet_url:
        sheet_id = sheet_url.split('/d/')[1].split('/')[0]
    else:
        sheet_id = sheet_url
    
    try:
        # Open the sheet
        sheet = gc.open_by_key(sheet_id)
        worksheet = sheet.sheet1  # Get first worksheet
        
        # Get all records
        records = worksheet.get_all_records()
        
        if not records:
            print("⚠️ No data found in the sheet")
            return 0
        
        # Parse contacts
        contacts = []
        for row in records:
            # Try different column names
            username = (
                row.get('SSYLKA') or 
                row.get('username') or 
                row.get('Username') or 
                row.get('USERNAME') or
                row.get('Ссылка') or
                row.get('ссылка') or
                ''
            )
            
            name = (
                row.get('NAME') or 
                row.get('name') or 
                row.get('Name') or 
                row.get('NAME') or
                row.get('Имя') or
                row.get('имя') or
                ''
            )
            
            description = (
                row.get('OPISANIYE') or 
                row.get('description') or 
                row.get('Description') or 
                row.get('DESCRIPTION') or
                row.get('Описание') or
                row.get('описание') or
                ''
            )
            
            if username:
                contacts.append({
                    'username': str(username),
                    'name': str(name),
                    'description': str(description)
                })
        
        # Import to database
        count = db.import_contacts_from_list(contacts, group_name)
        
        print(f"✅ Successfully imported {count} contacts from Google Sheets")
        print(f"   Group: {group_name}")
        
        return count
        
    except gspread.exceptions.SpreadsheetNotFound:
        print("❌ Error: Spreadsheet not found!")
        print("Make sure you shared the sheet with the service account email.")
        return 0
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 0


def import_from_csv(csv_path: str, group_name: str = "imported") -> int:
    """Import contacts from CSV file."""
    import pandas as pd
    
    try:
        df = pd.read_csv(csv_path)
        
        contacts = []
        for _, row in df.iterrows():
            username = str(row.get('username', row.get('SSYLKA', '')))
            name = str(row.get('name', row.get('NAME', '')))
            description = str(row.get('description', row.get('OPISANIYE', '')))
            
            if username:
                contacts.append({
                    'username': username,
                    'name': name,
                    'description': description
                })
        
        count = db.import_contacts_from_list(contacts, group_name)
        
        print(f"✅ Successfully imported {count} contacts from CSV")
        print(f"   Group: {group_name}")
        
        return count
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 0


def main():
    parser = argparse.ArgumentParser(description='Import contacts from Google Sheets or CSV')
    parser.add_argument('source', help='Google Sheets URL or CSV file path')
    parser.add_argument('--group', default='imported', help='Group name for imported contacts')
    
    args = parser.parse_args()
    
    # Initialize database
    db.init_db()
    
    # Check if source is a URL or file
    if args.source.startswith('http') or 'docs.google.com' in args.source:
        import_from_google_sheets(args.source, args.group)
    elif args.source.endswith('.csv'):
        import_from_csv(args.source, args.group)
    else:
        print("❌ Error: Invalid source. Provide a Google Sheets URL or CSV file path.")


if __name__ == '__main__':
    main()
