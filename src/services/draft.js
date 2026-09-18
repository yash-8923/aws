/**
 * Refactored Amazon Bedrock Draft Generation Service connecting to Python Backend
 */
export const mockGenerateDraft = async (captureData) => {
    console.log(`[Amazon Bedrock Draft via Python API] Generating drafted complaint...`);
    const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";

    try {
        const response = await fetch(`${BACKEND_URL}/api/draft`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify(captureData)
        });

        if (!response.ok) throw new Error("Backend API Error");
        return await response.json();
    } catch (error) {
        console.error("Draft Generation API failed:", error);
        throw error;
    }
};
