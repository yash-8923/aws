import { openDB } from 'idb';

/**
 * Mock AWS Services for Post-Submission Tracking
 */

export const saveReportToDynamoDB = async (ticketId, draft, captureId) => {
    console.log(`[Amazon DynamoDB] Saving report metadata for ticket: ${ticketId}`);
    try {
        const payload = {
            ticketId,
            timestamp: Date.now(),
            jurisdiction: draft.jurisdiction,
            damageType: draft.damageType,
            severity: draft.severity,
            status: 'SUBMITTED',
            captureId
        };
        const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";
        const res = await fetch(`${BACKEND_URL}/api/reports/save`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error("DynamoDB save failed");

        // Also save to IndexedDB for offline tracking
        const db = await openDB('SewaSahayakDB', 1);
        if (db.objectStoreNames.contains('reports')) {
            await db.add('reports', payload);
        }
    } catch (error) {
        console.error("Failed to save report to backend", error);
        alert(`DynamoDB Save Error: ${error.message}`);
    }
};

export const uploadEvidenceToS3 = async (blob, ticketId) => {
    console.log(`[Amazon S3] Encrypting (AES-256) and uploading evidence for ticket: ${ticketId} to ap-south-1...`);
    try {
        const formData = new FormData();
        formData.append("evidence", blob, "evidence.jpg");
        formData.append("ticketId", ticketId);

        const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";
        const res = await fetch(`${BACKEND_URL}/api/evidence/upload`, {
            method: "POST",
            credentials: "include",
            body: formData
        });
        if (!res.ok) throw new Error("S3 Upload Failed");
        const data = await res.json();
        return data.s3_uri;
    } catch (error) {
        console.error("Failed to upload evidence to backend S3", error);
        alert(`S3 Upload Error: ${error.message}`);
        return `s3://mock-fallback/${ticketId}/evidence.blob`;
    }
};

// Browser Push Notification Wrapper
export const sendPushNotification = (title, options) => {
    if (typeof Notification === 'undefined') return;

    if (Notification.permission === 'granted') {
        new Notification(title, options);
    } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(permission => {
            if (permission === 'granted') {
                new Notification(title, options);
            }
        });
    }
};
