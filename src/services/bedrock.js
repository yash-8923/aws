/**
 * Refactored Amazon Bedrock (Nova Pro) Service connecting to Python Backend
 */
export const mockAnalyzeMedia = async (mediaBlob, type = 'image') => {
    console.log(`[Amazon Bedrock Nova Pro via Python API] Sending media for analysis: ${type}`);
    const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";

    const formData = new FormData();
    formData.append('media', mediaBlob, `capture.${type === 'image' ? 'jpg' : 'mp4'}`);
    formData.append('type', type);

    try {
        const response = await fetch(`${BACKEND_URL}/api/analyze`, {
            method: 'POST',
            credentials: 'include',
            body: formData
        });

        if (!response.ok) throw new Error("Backend API Error");
        return await response.json();
    } catch (error) {
        console.error("Analysis API failed:", error);
        throw error;
    }
};
