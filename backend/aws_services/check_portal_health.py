import urllib.request
import urllib.error
import ssl
from typing import Optional

def check_portal_health(url: str) -> Optional[str]:
    """
    Sends a lightweight pre-flight HTTP request to the government portal.
    This runs before triggering the massive Playwright Chromium browser and AWS Bedrock Nova session.
    
    Returns:
        An error message if the portal is unreachable, otherwise None.
    """
    # Create an unverified SSL context for legacy govt portals
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    # This specific flag forces OpenSSL to allow connections to vulnerable/legacy servers
    ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT

    # Simulate a standard user agent to avoid basic blocks
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SewaSahayak/1.0'}
    )
    
    try:
        # Pre-flight check with a 10s timeout to save Nova Act tokens 
        urllib.request.urlopen(req, context=ctx, timeout=10)
        return None  # Portal is up
        
    except urllib.error.HTTPError as e:
        return f"Portal is offline or blocking requests (HTTP {e.code}: {e.reason})"
    except urllib.error.URLError as e:
        return f"Portal is unreachable (Network Error: {e.reason})"
    except Exception as e:
        return f"Portal health check failed: {str(e)}"

if __name__ == "__main__":
    # Test script if run directly
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://complaint.nhai.org/complaintsregistration/"
    print(f"Checking health for: {url}")
    error = check_portal_health(url)
    if error:
        print(f"FAILED: {error}")
    else:
        print("SUCCESS: Portal is reachable!")
