import boto3
import os
import json

# Updated for v2 Places API
REGION = os.getenv('AWS_REGION', 'ap-south-1')
# Client name is 'geo-places' for the new API
location_client = boto3.client('geo-places', region_name=REGION)

def reverse_geocode(lat: float, lng: float):
    """Scenario A: GPS Enabled - Using v2 reverse_geocode"""
    try:
        response = location_client.reverse_geocode(
            QueryPosition=[lng, lat], # [Longitude, Latitude]
            MaxResults=1
        )
        
        if response.get('ResultItems'):
            # V2 uses 'ResultItems' instead of 'Results'
            place = response['ResultItems'][0]
            address = place.get('Address', {})
            
            # Mapping based on your specific JSON response
            structured_address = {
                "Address": address.get('Label', ''),
                "City": address.get('Locality', ''), # 'Locality' is 'Bengaluru' in your JSON
                "District": address.get('District', ''),
                "State": address.get('Region', {}).get('Name', ''), # Accessing nested Region Name
                "PostalCode": address.get('PostalCode', ''),
                "Country": address.get('Country', {}).get('Name', '')
            }
            return structured_address
        return None
    except Exception as e:
        print(f"Reverse Geocode Error: {e}")
        return None

def verify_address(state: str, city: str, address: str):
    """Scenario B: No GPS - Using v2 geocode (text-to-coordinates)"""
    search_text = f"{address}, {city}, {state}, India"
    try:
        response = location_client.geocode(
            QueryText=search_text,
            MaxResults=1
        )
        
        if response.get('ResultItems'):
            place = response['ResultItems'][0]
            address_info = place.get('Address', {})
            
            structured_address = {
                "Address": address_info.get('Label', ''),
                "City": address_info.get('Locality', ''),
                "District": address_info.get('District', ''),
                "State": address_info.get('Region', {}).get('Name', ''),
                "PostalCode": address_info.get('PostalCode', ''),
                "Country": address_info.get('Country', {}).get('Name', '')
            }
            return structured_address
        return None
    except Exception as e:
        print(f"Verify Address Error: {e}")
        return None

# # Test the function
# print("--- Reverse Geocode Result ---")
# print(json.dumps(reverse_geocode(23.032693, 72.642445), indent=4))

# print("--- Verify Address Result ---")
# print(json.dumps(verify_address("Gujarat", "Ahmedabad", "patel"), indent=4))