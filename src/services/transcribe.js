/**
 * Refactored Transcribe Service connecting to Python Backend
 */
export const mockTranscribeAudio = async (audioBlob, language = 'hi-IN') => {
    console.log(`[AWS Transcribe via Python API] Sending audio for transcription...`);
    const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";

    const formData = new FormData();
    formData.append('audio', audioBlob, 'voice_note.webm');

    try {
        const response = await fetch(`${BACKEND_URL}/api/transcribe`, {
            method: 'POST',
            credentials: 'include',
            body: formData
        });

        if (!response.ok) throw new Error("Backend API Error");
        return await response.json();
    } catch (error) {
        console.error("Transcription API failed:", error);
        throw error;
    }
};
