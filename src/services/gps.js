/**
 * GPS Extraction and Jurisdiction Mapping Service
 * Uses real browser Geolocation API + backend routing
 */

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";

/**
 * Uses the real browser Geolocation API to get high-accuracy GPS coordinates.
 * Falls back gracefully if permissions are denied or unavailable.
 */
export const getDeviceLocation = async () => {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            console.warn("[GPS] Geolocation API not available in this browser.");
            reject(new Error("Geolocation is not supported by this browser."));
            return;
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const locationData = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                    accuracy: position.coords.accuracy,
                    altitude: position.coords.altitude,
                    speed: position.coords.speed,
                    timestamp: position.timestamp
                };
                console.log(`[GPS] Real location acquired: (${locationData.lat.toFixed(6)}, ${locationData.lng.toFixed(6)}) ±${locationData.accuracy.toFixed(0)}m`);
                resolve(locationData);
            },
            (error) => {
                let reason;
                switch (error.code) {
                    case error.PERMISSION_DENIED:
                        reason = "Location permission denied by user.";
                        break;
                    case error.POSITION_UNAVAILABLE:
                        reason = "Location information unavailable.";
                        break;
                    case error.TIMEOUT:
                        reason = "Location request timed out.";
                        break;
                    default:
                        reason = `Unknown error: ${error.message}`;
                }
                console.warn(`[GPS] Failed to get location: ${reason}`);
                reject(new Error(reason));
            },
            {
                enableHighAccuracy: true,   // Use GPS hardware if available
                timeout: 15000,             // Wait up to 15 seconds
                maximumAge: 60000           // Accept cached position up to 1 minute old
            }
        );
    });
};

/**
 * Maps GPS coordinates to a government jurisdiction by calling the backend's
 * cognitive dispatcher (/api/route), which uses real AWS Location Service
 * for reverse geocoding and Amazon Bedrock for portal routing.
 */
export const mapJurisdiction = async (lat, lng) => {
    console.log(`[Jurisdiction] Routing via backend for: (${lat}, ${lng})`);

    try {
        const res = await fetch(`${BACKEND_URL}/api/route`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify({ lat, lng })
        });

        if (!res.ok) {
            throw new Error(`Backend routing failed: HTTP ${res.status}`);
        }

        const data = await res.json();
        const routing = data.routing || {};
        const address = data.structured_address || {};

        return {
            jurisdiction_level: routing.portal_name?.includes("Municipal") ? "Municipal"
                : routing.portal_name?.includes("NHAI") ? "Central" : "State",
            portal_name: routing.portal_name || "Government Portal",
            portal_url: routing.portal_url || "",
            ward_district: address.District || address.City || "Unknown",
            reasoning: routing.reasoning || "",
            mapped_coordinates: { lat, lng }
        };

    } catch (err) {
        console.error("[Jurisdiction] Backend routing error, using fallback:", err);
        // Fallback: return a generic result so the app doesn't break
        return {
            jurisdiction_level: "Unknown",
            portal_name: "CPGRAMS (Central)",
            portal_url: "https://pgportal.gov.in/Registration",
            ward_district: "Unknown",
            reasoning: "Fallback — backend routing unavailable.",
            mapped_coordinates: { lat, lng }
        };
    }
};
