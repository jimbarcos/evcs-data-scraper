#!/usr/bin/env python3
"""
EVCS Data Scraper with Email Notifications
Converts the Jupyter notebook functionality to a standalone script
for GitHub Actions workflow execution.

Author: JIM AEROL S. BARCOS
Last Modified: July 27, 2025
"""

import sys
import time
import json
import gzip
import os
import glob
import pandas as pd
import copy
import smtplib
import traceback
from urllib.parse import unquote
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

try:
    import brotli
except ImportError:
    brotli = None

try:
    import sib_api_v3_sdk
    from sib_api_v3_sdk.rest import ApiException
    SENDINBLUE_AVAILABLE = True
except ImportError:
    SENDINBLUE_AVAILABLE = False

from seleniumwire import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By

# Load environment variables
load_dotenv()

class EVCSScraper:
    def __init__(self):
        self.driver = None
        self.email_api_key = os.getenv('EMAIL_API_KEY')
        self.notification_email = os.getenv('NOTIFICATION_EMAIL', 'jimbarcos01@gmail.com')  # Default email
        self.output_files = []
        self.error_log = []
        
    def setup_driver(self):
        """Setup and configure the Edge WebDriver"""
        print("Setting up Edge WebDriver...")
        
        edge_options = EdgeOptions()
        edge_options.add_argument("--headless")
        edge_options.add_argument("--disable-gpu")
        edge_options.add_argument("--window-size=1920,1080")
        edge_options.add_argument("--no-sandbox")
        edge_options.add_argument("--disable-dev-shm-usage")
        edge_options.add_argument("--disable-extensions")
        edge_options.add_argument("--disable-web-security")
        edge_options.add_argument("--allow-running-insecure-content")
        
        # Try to find EdgeDriver in different locations
        driver_paths = [
            "/usr/local/bin/msedgedriver",  # GitHub Actions
            "./Driver_Notes/msedgedriver.exe",  # Local Windows
            "./Driver_Notes/msedgedriver",  # Local Linux
            "msedgedriver"  # System PATH
        ]
        
        driver_path = None
        for path in driver_paths:
            if os.path.exists(path):
                driver_path = path
                break
        
        try:
            if driver_path:
                edge_service = EdgeService(executable_path=driver_path)
                self.driver = webdriver.Edge(service=edge_service, options=edge_options)
            else:
                # Let selenium-wire find the driver automatically
                self.driver = webdriver.Edge(options=edge_options)
            print("✓ Edge WebDriver initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize Edge WebDriver: {str(e)}"
            print(f"✗ {error_msg}")
            self.error_log.append(error_msg)
            raise
    
    def scrape_evcs_data(self):
        """Main scraping function"""
        print("Starting EVCS data scraping...")
        
        url = "https://evindustry.ph/evcs-locations"
        self.driver.get(url)
        time.sleep(5)
        
        # Extract CSRF token
        csrf_token = self.driver.execute_script(
            "return document.querySelector('meta[name=csrf-token]')?.content || "
            "document.querySelector('input[name=_token]')?.value || null;"
        )
        
        if not csrf_token:
            for cookie in self.driver.get_cookies():
                if cookie['name'] == 'XSRF-TOKEN':
                    csrf_token = unquote(cookie['value'])
                    break
        
        if not csrf_token:
            error_msg = "CSRF token not found!"
            self.error_log.append(error_msg)
            raise Exception(error_msg)
        
        print("✓ CSRF token extracted")
        
        # Scroll to trigger lazy loading
        print("Triggering lazy loading by scrolling...")
        SCROLL_PAUSE_TIME = 2
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        for i in range(10):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(SCROLL_PAUSE_TIME)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print(f"✓ Lazy loading complete after {i+1} scrolls")
                break
            last_height = new_height
        
        return self.extract_station_data()
    
    def extract_station_data(self):
        """Extract and parse station data from network requests"""
        print("Extracting station data from network requests...")
        
        all_stations_dict = {}
        
        for request in self.driver.requests:
            if (request.response and 
                request.url == "https://evindustry.ph/evcs-locations" and 
                'application/json' in request.response.headers.get('Content-Type', '')):
                
                try:
                    raw_bytes = request.response.body
                    
                    # Try to decompress the response
                    try:
                        decompressed = gzip.decompress(raw_bytes).decode('utf-8', errors='ignore')
                        data = decompressed
                    except Exception:
                        if brotli:
                            try:
                                decompressed = brotli.decompress(raw_bytes).decode('utf-8', errors='ignore')
                                data = decompressed
                            except Exception:
                                data = raw_bytes.decode('utf-8', errors='ignore')
                        else:
                            data = raw_bytes.decode('utf-8', errors='ignore')
                    
                    json_data = json.loads(data)
                    
                    if (isinstance(json_data, dict) and 
                        'props' in json_data and 
                        'chargepoints' in json_data['props']):
                        
                        for cp in json_data['props']['chargepoints']:
                            if 'station' in cp:
                                station = cp['station']
                                station_id = station.get('id') or station.get('station_id')
                                
                                if not station_id:
                                    continue
                                
                                if station_id not in all_stations_dict:
                                    station_copy = station.copy()
                                    station_copy['chargepoints'] = []
                                    all_stations_dict[station_id] = station_copy
                                
                                all_stations_dict[station_id]['chargepoints'].append(cp)
                                
                except Exception as e:
                    error_msg = f"Error parsing /evcs-locations JSON: {e}"
                    print(f"⚠ {error_msg}")
                    self.error_log.append(error_msg)
        
        all_stations = list(all_stations_dict.values())
        
        if not all_stations:
            error_msg = "No station data found!"
            self.error_log.append(error_msg)
            raise Exception(error_msg)
        
        print(f"✓ Extracted {len(all_stations)} stations")
        return all_stations
    
    def save_json_data(self, stations_data):
        """Save station data to JSON file"""
        now = datetime.now()
        dt_str = now.strftime("%B_%d_%Y_%H_%M")
        json_filename = f"evcs_data_{dt_str}.json"
        
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(stations_data, f, ensure_ascii=False, indent=2)
        
        self.output_files.append(json_filename)
        print(f"✓ JSON data saved to {json_filename}")
        return json_filename, dt_str
    
    def extract_chargepoints(self, station):
        """Extract chargepoints from station data"""
        cps = station.get('chargepoints')
        if not cps or not isinstance(cps, list):
            return []
        
        if cps and isinstance(cps[0], dict) and ('mode' in cps[0] or 'id_or_serial_number' in cps[0]):
            return cps
        
        flat = []
        for item in cps:
            if isinstance(item, dict) and 'chargepoints' in item and isinstance(item['chargepoints'], list):
                flat.extend(item['chargepoints'])
        
        return flat
    
    def process_and_export_data(self, stations_data, base_name):
        """Process station data and export to Excel/CSV"""
        print("Processing and exporting data...")
        
        # Add charging summaries to stations
        for station in stations_data:
            cps = self.extract_chargepoints(station)
            protocols = set()
            modes = set()
            equipments = set()
            
            for cp in cps:
                # Protocols
                protocol = cp.get('charging_protocol')
                if isinstance(protocol, list):
                    for p in protocol:
                        protocols.add(str(p))
                elif protocol:
                    protocols.add(str(protocol))
                
                # Equipment
                equipment = (cp.get('id_or_serial_number') or 
                           cp.get('equipment') or 
                           cp.get('name'))
                if equipment:
                    equipments.add(str(equipment))
                
                # Mode
                mode = cp.get('mode') or cp.get('evcs_mode')
                if mode:
                    modes.add(str(mode))
            
            station['Charging Protocols'] = ', '.join(sorted(protocols))
            station['EVCS Modes'] = ', '.join(sorted(modes))
            station['Charging Equipments'] = ', '.join(sorted(equipments))
            
            # Remove chargepoints_summary if exists
            if 'chargepoints_summary' in station:
                del station['chargepoints_summary']
        
        # Create aggregated DataFrame
        stations_df = pd.json_normalize(stations_data)
        if 'chargepoints' in stations_df.columns:
            stations_df = stations_df.drop(columns=['chargepoints'])
        
        # Export aggregated data
        excel_filename = f"{base_name}.xlsx"
        csv_filename = f"{base_name}.csv"
        
        stations_df.to_excel(excel_filename, index=False)
        stations_df.to_csv(csv_filename, index=False)
        
        self.output_files.extend([excel_filename, csv_filename])
        print(f"✓ Aggregated data saved to {excel_filename} and {csv_filename}")
        
        # Create flattened DataFrame (one row per charging equipment)
        flat_rows = []
        for station in stations_data:
            base = copy.deepcopy(station)
            cps = self.extract_chargepoints(station)
            
            if cps:
                for cp in cps:
                    row = copy.deepcopy(base)
                    row['Charging Equipment'] = (cp.get('id_or_serial_number') or 
                                                cp.get('equipment') or 
                                                cp.get('name'))
                    row['Charging Protocol'] = cp.get('charging_protocol')
                    row['EVCS mode'] = cp.get('mode') or cp.get('evcs_mode')
                    flat_rows.append(row)
            else:
                row = copy.deepcopy(base)
                row['Charging Equipment'] = ''
                row['Charging Protocol'] = ''
                row['EVCS mode'] = ''
                flat_rows.append(row)
        
        flat_df = pd.DataFrame(flat_rows)
        
        # Reorder columns for priority
        priority_cols = [
            'station_id', 'company_id', 'evcs_establishment_name', 
            'Charging Protocol', 'Charging Equipment', 'EVCS mode', 'region'
        ]
        other_cols = [col for col in flat_df.columns if col not in priority_cols]
        flat_df = flat_df[priority_cols + other_cols]
        
        # Export flattened data
        flat_excel = f"{base_name}_flat.xlsx"
        flat_csv = f"{base_name}_flat.csv"
        
        flat_df.to_excel(flat_excel, index=False)
        flat_df.to_csv(flat_csv, index=False)
        
        self.output_files.extend([flat_excel, flat_csv])
        print(f"✓ Flattened data saved to {flat_excel} and {flat_csv}")
        
        return len(stations_data), len(flat_rows)
    
    def send_email_notification(self, success=True, stations_count=0, chargepoints_count=0, error_details=None):
        """Send email notification with results"""
        if not self.email_api_key or not SENDINBLUE_AVAILABLE:
            print("⚠ Email notification skipped - API key not configured or SendinBlue not available")
            return
        
        print("Sending email notification...")
        
        try:
            # Configure SendinBlue API
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key['api-key'] = self.email_api_key
            api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
            
            # Prepare email content
            now = datetime.now()
            timestamp = now.strftime("%B %d, %Y at %H:%M UTC")
            
            if success:
                subject = f"✅ EVCS Scraper Success - {stations_count} stations processed"
                html_content = f"""
                <html>
                <body>
                    <h2>🚗⚡ EVCS Data Scraping Completed Successfully</h2>
                    <p><strong>Execution Time:</strong> {timestamp}</p>
                    <p><strong>Results:</strong></p>
                    <ul>
                        <li>Stations processed: {stations_count}</li>
                        <li>Charging points processed: {chargepoints_count}</li>
                        <li>Output files generated: {len(self.output_files)}</li>
                    </ul>
                    <p><strong>Generated Files:</strong></p>
                    <ul>
                        {''.join([f"<li>{file}</li>" for file in self.output_files])}
                    </ul>
                    {"<p><strong>Warnings:</strong></p><ul>" + ''.join([f"<li>{error}</li>" for error in self.error_log]) + "</ul>" if self.error_log else ""}
                    <p>All output files are attached to this email.</p>
                    <hr>
                    <p><em>This is an automated message from the EVCS Data Scraper.</em></p>
                </body>
                </html>
                """
            else:
                subject = f"❌ EVCS Scraper Failed - {timestamp}"
                html_content = f"""
                <html>
                <body>
                    <h2>🚨 EVCS Data Scraping Failed</h2>
                    <p><strong>Execution Time:</strong> {timestamp}</p>
                    <p><strong>Error Details:</strong></p>
                    <pre>{error_details}</pre>
                    {"<p><strong>Additional Errors:</strong></p><ul>" + ''.join([f"<li>{error}</li>" for error in self.error_log]) + "</ul>" if self.error_log else ""}
                    {"<p><strong>Partial Files Generated:</strong></p><ul>" + ''.join([f"<li>{file}</li>" for file in self.output_files]) + "</ul>" if self.output_files else "<p>No files were generated.</p>"}
                    <hr>
                    <p><em>This is an automated message from the EVCS Data Scraper.</em></p>
                </body>
                </html>
                """
            
            # Prepare attachments
            attachments = []
            for file_path in self.output_files:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    attachment = {
                        "content": content,
                        "name": os.path.basename(file_path)
                    }
                    attachments.append(attachment)
            
            # Send email
            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                to=[{"email": self.notification_email}],
                subject=subject,
                html_content=html_content,
                sender={"name": "EVCS Scraper", "email": "jimbarcos01@gmail.com"},
                attachment=attachments if attachments else None
            )
            
            api_response = api_instance.send_transac_email(send_smtp_email)
            print(f"✓ Email notification sent successfully (Message ID: {api_response.message_id})")
            
        except ApiException as e:
            error_msg = f"SendinBlue API error: {e}"
            print(f"✗ {error_msg}")
            self.error_log.append(error_msg)
        except Exception as e:
            error_msg = f"Email notification error: {e}"
            print(f"✗ {error_msg}")
            self.error_log.append(error_msg)
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            print("✓ WebDriver closed")
    
    def run(self):
        """Main execution method"""
        stations_count = 0
        chargepoints_count = 0
        error_details = None
        
        try:
            print("🚗⚡ Starting EVCS Data Scraper...")
            print(f"Timestamp: {datetime.now().strftime('%B %d, %Y at %H:%M:%S UTC')}")
            print("-" * 60)
            
            # Setup and run scraper
            self.setup_driver()
            stations_data = self.scrape_evcs_data()
            json_filename, dt_str = self.save_json_data(stations_data)
            base_name = f"evcs_data_{dt_str}"
            stations_count, chargepoints_count = self.process_and_export_data(stations_data, base_name)
            
            print("-" * 60)
            print(f"✅ Scraping completed successfully!")
            print(f"📊 Processed {stations_count} stations and {chargepoints_count} charging points")
            print(f"📁 Generated {len(self.output_files)} output files")
            
            # Send success notification
            self.send_email_notification(
                success=True, 
                stations_count=stations_count, 
                chargepoints_count=chargepoints_count
            )
            
        except Exception as e:
            error_details = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            print(f"\n❌ Scraping failed: {str(e)}")
            print(f"Full error details:\n{error_details}")
            
            # Send failure notification
            self.send_email_notification(success=False, error_details=error_details)
            
            return 1  # Exit code for failure
        
        finally:
            self.cleanup()
        
        return 0  # Exit code for success


if __name__ == "__main__":
    scraper = EVCSScraper()
    exit_code = scraper.run()
    sys.exit(exit_code)
