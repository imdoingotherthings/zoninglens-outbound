import os
import re
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("API_URL", "https://api.zoninglens.com")
JWT_TOKEN = os.getenv("JWT_TOKEN")
ADMIN_SECRET = os.getenv("ADMIN_SECRET")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
CF_CLIENT_ID = os.getenv("CF_CLIENT_ID")
CF_CLIENT_SECRET = os.getenv("CF_CLIENT_SECRET")

SENDER_EMAIL = "ZoningLens Intel <welcome@updates.zoninglens.com>"

def slugify(text):
    text = str(text).lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    return re.sub(r'[\s-]+', '-', text).strip('-')

def format_and_check_date(raw_date):
    """Cleans the date and returns (formatted_string, days_old)"""
    if not raw_date: return "Recent", 0
    
    # Strip messy characters
    cleaned = re.sub(r'\$|[a-zA-Z]$', '', raw_date).strip()
    match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', cleaned)
    
    if match:
        date_str = match.group(1)
        try:
            dt = datetime.strptime(date_str, "%m/%d/%Y")
            formatted = dt.strftime("%B %d, %Y")
            days_old = (datetime.now() - dt).days
            return formatted, days_old
        except ValueError:
            pass
            
    return cleaned, 0

def run_outbound_campaign():
    print("\n🚀 Booting ZoningLens Outbound Sales Engine...\n")

    parcels_res = requests.get(f"{API_URL}/api/parcels", headers={"Authorization": f"Bearer {JWT_TOKEN}"})
    if parcels_res.status_code != 200: return print("❌ API Error (Parcels)")
    parcels = parcels_res.json()

    leads_res = requests.get(
        "https://zoningdash.qleapventures.com/api/leads", 
        headers={
            "CF-Access-Client-Id": CF_CLIENT_ID,
            "CF-Access-Client-Secret": CF_CLIENT_SECRET
        }
    )

    if leads_res.status_code != 200: return print("❌ API Error (Leads)")
    leads = leads_res.json()

    if not leads or not parcels:
        print("\n🔍 SYSTEM DIAGNOSTICS:")
        print(f"🌍 Target API: {API_URL}")
        print(f"📦 Parcels Payload: {parcels if not isinstance(parcels, list) else f'{len(parcels)} records'}")
        print(f"🎯 Leads Payload: {leads if not isinstance(leads, list) else f'{len(leads)} records'}")
        return print("\n⚠️ Missing data. Exiting.")

    for broker in leads:
       status = broker.get('status', 'New').lower()
        if status in ['dead', 'replied']:
            continue
            
        contact_name = broker.get('contact_name', 'Broker').split(' ')[0]
        company = broker.get('company_name', 'your firm')
        email = broker.get('email')
        
        keyword_string = broker.get("keywords") or "commercial"
        broker_keywords = [k.strip().lower() for k in keyword_string.split(',')]
        
        # Gather all matching, recent parcels for THIS broker
        matched_parcels = []
        
        for parcel in parcels:
            opp_type = parcel.get("opportunity_type", "").lower()
            if any(kw in opp_type for kw in broker_keywords):
                
                clean_date, days_old = format_and_check_date(parcel.get("meeting_date"))
                
                # STRICT FILTER: Skip if older than 90 days (you can change this number)
                if days_old > 90:
                    continue 
                
                matched_parcels.append({
                    "address": parcel.get("address", "Unknown"),
                    "type": parcel.get('opportunity_type'),
                    "date": clean_date,
                    "link": f"https://zoninglens.com/zoning/{slugify(parcel.get('address'))}",
                    "source": parcel.get("source_url", "#")
                })

        if not matched_parcels:
            print(f"⏭️ {contact_name} at {company} - No recent matches found.")
            continue

        # We have matches! Build ONE digest email.
        subject = f"[{len(matched_parcels)} Targets] Pre-Market Zoning Activity in Torrance"
        
        html_body = f"""
        <div style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.6; max-width: 600px;">
            <p>Hi {contact_name},</p>
            <p>Knowing that <strong>{company}</strong> tracks high-value commercial opportunities across the South Bay market, I wanted to put this on your radar.</p>
            <p>My systems just intercepted <strong>{len(matched_parcels)} new municipal filings</strong> in Torrance that specifically match your asset class focus.</p>
        """                 

        for p in matched_parcels:
            html_body += f"""
            <div style="background-color: #f8fafc; border-left: 4px solid #1E3A8A; padding: 16px; margin: 20px 0;">
                <p style="margin: 0 0 8px 0;"><strong>Target:</strong> {p['address']}</p>
                <p style="margin: 0 0 12px 0;"><strong>Designation:</strong> {p['type']}</p>
                
                <p style="margin: 0 0 14px 0;">
                    <span style="background-color: #e2e8f0; color: #475569; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; letter-spacing: 0.5px; text-transform: uppercase;">
                        Filing Date: {p['date']}
                    </span>
                </p>
                
                <p style="margin: 0; font-size: 13px;">
                    <a href="{p['source']}" style="color: #64748b; text-decoration: none;">Verify Primary Source &rarr;</a> &nbsp;|&nbsp; 
                    <a href="{p['link']}" style="color: #1E3A8A; font-weight: bold; text-decoration: none;">View Intel Brief &rarr;</a>
                </p>
            </div>
            """
            
        html_body += """
            <p>Let me know if you want the full entity breakdown and interactive map unlocked on your dashboard.</p>
            <p>Best,<br><strong>Asai Andrade</strong><br>Founder, ZoningLens</p>
        </div>
        """

        print("\n=======================================================")
        print(f"🎯 DIGEST PREPARED: {len(matched_parcels)} properties -> {email}")
        print("=======================================================")
        
        action = input("🔥 Fire this digest email? (y/n/q to quit): ").strip().lower()
        
        if action == 'q': return print("🛑 Aborted.")
        elif action == 'y':
            resend_payload = {"from": SENDER_EMAIL, "to": email, "reply_to": "zoninglens@gmail.com", "subject": subject, "html": html_body}
            fire_req = requests.post("https://api.resend.com/emails", json=resend_payload, headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"})
            if fire_req.status_code == 200: print(f"✅ Fired successfully to {email}!\n")
            else: print(f"❌ Error: {fire_req.text}\n")
        else: print("⏭️ Skipped.\n")

if __name__ == "__main__":
    run_outbound_campaign()
