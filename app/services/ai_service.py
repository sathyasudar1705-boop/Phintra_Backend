import re
import urllib.parse
from typing import Dict, Any, List

def analyze_email_risk(subject: str, sender: str, body: str) -> Dict[str, Any]:
    """
    Scans a reported email and calculates its phishing risk score, risk level,
    detection categories, and outputs detailed assessment explanations.
    
    Returns a dictionary of:
    - risk_score (0-100)
    - risk_level (Low, Medium, High, Critical)
    - categories (dictionary of matching keyword list, link list, and logic triggers)
    - reasons (list of text justifications)
    """
    score = 0
    reasons = []
    suspicious_keywords = []
    suspicious_urls = []
    categories = {
        "phishing_keywords": [],
        "suspicious_urls": [],
        "urgency_language": [],
        "credential_theft_attempts": [],
        "banking_payment_scams": []
    }
    
    # 1. Analyze Sender Domain and Cues
    sender_lower = sender.lower()
    if "@" in sender_lower:
        domain = sender_lower.split("@")[-1]
        # Check for free webmail domains
        free_domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com", "mail.com", "yandex.com", "zoho.com"]
        if any(f == domain for f in free_domains):
            score += 15
            reasons.append("Sender utilizes a public email provider (e.g. Gmail, Yahoo) instead of a corporate domain.")
        
        # Check for lookalike branding/admin cues in the username part of the email
        username = sender_lower.split("@")[0]
        lookalikes = ["support", "security", "admin", "billing", "verify", "secure", "update", "service", "system", "accounts"]
        found_sender_keywords = [w for w in lookalikes if w in username]
        if found_sender_keywords:
            score += 10 * len(found_sender_keywords)
            reasons.append(f"Sender username contains administrative/system keywords: {', '.join(found_sender_keywords)}")
            
    # 2. Scan Subject & Body Content for typical Phishing Cues
    phishing_keywords_map = {
        "urgency": ["urgent", "action required", "immediate", "suspension", "expire", "unauthorized", "limited time", "act now", "critical security", "important update"],
        "credential_theft": ["login", "password reset", "verify your account", "confirm credentials", "sign in", "update your password", "security alert", "unusual sign-in activity", "access suspended"],
        "banking": ["invoice", "payment", "wire transfer", "bank transfer", "refund", "receipt", "overdue", "billing update", "credit card", "payroll", "bonus", "salary"]
    }
    
    content_to_scan = f"{subject} {body}".lower()
    
    # Check for Urgency Language
    found_urgency = [w for w in phishing_keywords_map["urgency"] if w in content_to_scan]
    if found_urgency:
        score += 20 + (5 * len(found_urgency))
        categories["urgency_language"].extend(found_urgency)
        reasons.append(f"Urgent/high-pressure language detected: {', '.join(found_urgency)}")
        
    # Check for Credential Theft attempts
    found_credentials = [w for w in phishing_keywords_map["credential_theft"] if w in content_to_scan]
    if found_credentials:
        score += 25 + (5 * len(found_credentials))
        categories["credential_theft_attempts"].extend(found_credentials)
        reasons.append(f"Credential harvesting indicators found: {', '.join(found_credentials)}")
        
    # Check for Banking/Financial scams
    found_banking = [w for w in phishing_keywords_map["banking"] if w in content_to_scan]
    if found_banking:
        score += 20 + (5 * len(found_banking))
        categories["banking_payment_scams"].extend(found_banking)
        reasons.append(f"Financial transaction or scam keywords detected: {', '.join(found_banking)}")
        
    # Collate all suspicious keywords detected
    suspicious_keywords = list(set(found_urgency + found_credentials + found_banking))
    categories["phishing_keywords"] = suspicious_keywords

    # 3. Analyze Link URLs inside the Body
    # Simple regex to extract links
    urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', body)
    for url in urls:
        try:
            # Normalize url format
            full_url = url if url.startswith("http") else f"http://{url}"
            parsed = urllib.parse.urlparse(full_url)
            netloc = parsed.netloc or parsed.path.split("/")[0]
            
            if netloc:
                netloc_lower = netloc.lower()
                # Check for suspicious TLDs
                susp_tlds = [".xyz", ".info", ".top", ".club", ".click", ".work", ".ru", ".cn", ".bid", ".live", ".fit", ".gq", ".cf", ".tk", ".ml"]
                if any(netloc_lower.endswith(tld) or tld + "/" in netloc_lower for tld in susp_tlds):
                    score += 15
                    suspicious_urls.append(url)
                    reasons.append(f"URL contains a suspicious/low-reputation top-level domain: '{url}'")
                    
                # Direct IP Address check
                # Check if host matches a numeric IP representation
                host_only = netloc_lower.split(":")[0]
                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host_only):
                    score += 25
                    suspicious_urls.append(url)
                    reasons.append(f"URL uses a direct IP address instead of a domain name: '{url}'")
                    
                # Lookalike branding cues in third-party links
                lookalike_keywords = ["login", "signin", "verify", "secure", "update", "account", "banking", "support", "paypal", "microsoft", "google", "office365", "outlook"]
                legit_domains = ["microsoft.com", "google.com", "paypal.com", "office.com", "live.com"]
                
                # If it mentions lookalike branding but isn't on a legitimate domain
                if any(kw in netloc_lower for kw in lookalike_keywords) and not any(legit in netloc_lower for legit in legit_domains):
                    score += 20
                    suspicious_urls.append(url)
                    reasons.append(f"URL host contains corporate/branding keywords but resides on an external domain: '{netloc}'")
        except Exception:
            pass

    categories["suspicious_urls"] = list(set(suspicious_urls))
    
    # Cap score at 100
    score = min(score, 100)
    # Floor score at 0
    score = max(score, 0)
    
    # Assign Risk Level
    if score >= 85:
        risk_level = "Critical"
    elif score >= 65:
        risk_level = "High"
    elif score >= 35:
        risk_level = "Medium"
    else:
        risk_level = "Low"
        
    # If no warnings triggered, default reason
    if not reasons:
        reasons.append("No suspicious indicators, urgent terminology, or risky links detected in the subject/body.")
        
    return {
        "risk_score": score,
        "risk_level": risk_level,
        "categories": categories,
        "reasons": reasons
    }
