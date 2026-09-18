import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Video, StopCircle, UploadCloud, CheckCircle, AlertCircle } from 'lucide-react';
import { saveDashcamSegment, getUnsyncedDashcamSegments, markDashcamSegmentAsSynced } from '../utils/db';
import { useOnlineStatus } from '../hooks/useOnlineStatus';
import { getDeviceLocation } from '../services/gps';

const DashcamRecorder = () => {
    const videoRef = useRef(null);
    const mediaRecorderRef = useRef(null);
    const streamRef = useRef(null);
    const isOnline = useOnlineStatus();
    const syncInFlightRef = useRef(false);
    const pendingStopRef = useRef(Promise.resolve());

    const [isRecording, setIsRecording] = useState(false);
    const [segmentsCount, setSegmentsCount] = useState(0);
    const [unsyncedCount, setUnsyncedCount] = useState(0);
    const [isUploading, setIsUploading] = useState(false);
    const [errorMSG, setErrorMSG] = useState(null);

    // Initialize camera
    const startCamera = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: { ideal: 'environment' },
                    width: { ideal: 640, max: 960 },
                    height: { ideal: 360, max: 540 },
                    frameRate: { ideal: 15, max: 20 }
                },
                audio: false
            });
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
            }
            streamRef.current = stream;
            setErrorMSG(null);
        } catch (err) {
            console.error("Error accessing camera:", err);
            setErrorMSG("Could not access the camera. Please allow permissions.");
        }
    };

    useEffect(() => {
        startCamera();
        return () => {
            if (cycleIntervalRef.current) {
                clearInterval(cycleIntervalRef.current);
            }
            if (streamRef.current) {
                streamRef.current.getTracks().forEach(track => track.stop());
            }
        };
    }, []);

    // Sync background loop
    const syncSegments = useCallback(async () => {
        if (!isOnline) return;
        if (syncInFlightRef.current) return;
        const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";
        try {
            syncInFlightRef.current = true;
            setIsUploading(true);
            const unsynced = await getUnsyncedDashcamSegments();
            setUnsyncedCount(unsynced.length);

            if (unsynced.length === 0) {
                return;
            }

            for (const segment of unsynced) {
                try {
                    const formData = new FormData();
                    const ext = (segment.mimeType || 'video/webm').includes('mp4') ? 'mp4' : 'webm';
                    formData.append('segment', segment.blob, `dashcam_${segment.id}.${ext}`);
                    if (segment.lat != null) formData.append('lat', String(segment.lat));
                    if (segment.lng != null) formData.append('lng', String(segment.lng));

                    const res = await fetch(`${BACKEND_URL}/api/dashcam/upload`, {
                        method: 'POST',
                        body: formData,
                        credentials: 'include'
                    });

                    if (res.ok) {
                        await markDashcamSegmentAsSynced(segment.id);
                    }
                } catch (uploadErr) {
                    console.error(`Network error uploading segment ${segment.id}:`, uploadErr);
                }
            }

            const remaining = await getUnsyncedDashcamSegments();
            setUnsyncedCount(remaining.length);
        } catch (err) {
            console.error("Error during sync iteration", err);
        } finally {
            setIsUploading(false);
            syncInFlightRef.current = false;
        }
    }, [isOnline]);

    useEffect(() => {
        let intervalId;
        if (isOnline) {
            syncSegments();
            intervalId = setInterval(syncSegments, 5000);
        }
        return () => clearInterval(intervalId);
    }, [isOnline, syncSegments]);

    const cycleIntervalRef = useRef(null);
    const selectedTypeRef = useRef('');

    const startSingleRecording = useCallback(() => {
        if (!streamRef.current) return;

        const chunks = [];
        const recorder = new MediaRecorder(streamRef.current, {
            mimeType: selectedTypeRef.current,
            videoBitsPerSecond: 450_000
        });

        recorder.ondataavailable = (event) => {
            if (event.data && event.data.size > 0) chunks.push(event.data);
        };

        let resolveStopped;
        pendingStopRef.current = new Promise((resolve) => {
            resolveStopped = resolve;
        });

        recorder.onstop = async () => {
            try {
                if (chunks.length === 0) return;
                const completeBlob = new Blob(chunks, { type: selectedTypeRef.current });

                let loc = null;
                try { loc = await getDeviceLocation(); } catch { /* ignore */ }

                await saveDashcamSegment(completeBlob, {
                    mimeType: selectedTypeRef.current,
                    lat: loc?.lat,
                    lng: loc?.lng
                });

                setSegmentsCount(prev => prev + 1);
                setUnsyncedCount(prev => prev + 1);
                if (navigator.onLine) await syncSegments();
            } finally {
                if (resolveStopped) resolveStopped();
            }
        };

        recorder.start(1000);
        mediaRecorderRef.current = recorder;
    }, [syncSegments]);

    const toggleRecording = async () => {
        if (isRecording) {
            if (cycleIntervalRef.current) {
                clearInterval(cycleIntervalRef.current);
                cycleIntervalRef.current = null;
            }
            const pendingStop = pendingStopRef.current;
            if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
                mediaRecorderRef.current.stop();
            }
            setIsRecording(false);

            // Ensure the last segment is saved to IndexedDB, then flush the queue.
            try {
                await pendingStop;
            } catch {
                /* ignore */
            }
            if (navigator.onLine) await syncSegments();
            return;
        }

        if (!streamRef.current) {
            await startCamera();
            if (!streamRef.current) return;
        }

        try {
            const types = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'];
            selectedTypeRef.current = '';
            for (const t of types) {
                if (MediaRecorder.isTypeSupported(t)) {
                    selectedTypeRef.current = t;
                    break;
                }
            }

            // Flush any queued segments when monitoring starts again.
            if (navigator.onLine) await syncSegments();

            setIsRecording(true);
            setSegmentsCount(0);
            startSingleRecording();
            cycleIntervalRef.current = setInterval(() => {
                if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
                    mediaRecorderRef.current.stop();
                }
                startSingleRecording();
            }, 5000);

        } catch {
            setErrorMSG("Failed to start recording.");
        }
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {errorMSG && (
                <div style={{ background: 'rgba(239, 68, 68, 0.1)', color: 'var(--color-danger)', padding: '1rem', borderRadius: '12px', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <AlertCircle size={18} /> {errorMSG}
                </div>
            )}

            <div style={{ position: 'relative', width: '100%', aspectRatio: '16/9', background: '#000', borderRadius: '24px', overflow: 'hidden', border: '1px solid rgba(255,255,255,0.05)' }}>
                <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />

                {/* Status Overlay */}
                <div style={{ position: 'absolute', top: '1rem', left: '1rem', display: 'flex', gap: '0.5rem' }}>
                    {isRecording && (
                        <div style={{ background: 'var(--color-danger)', color: 'white', padding: '4px 12px', borderRadius: '50px', fontSize: '0.75rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <div style={{ width: '8px', height: '8px', background: 'white', borderRadius: '50%', animation: 'flash 1s infinite' }}></div>
                            LIVE REC
                        </div>
                    )}
                    <div style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(10px)', color: 'white', padding: '4px 12px', borderRadius: '50px', fontSize: '0.75rem', fontWeight: 600 }}>
                        {segmentsCount} SEGMENTS
                    </div>
                </div>


            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1rem', borderRadius: '16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ color: 'var(--color-primary)' }}><Video size={20} /></div>
                    <div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '1px' }}>Segments</div>
                        <div style={{ fontSize: '1.1rem', fontWeight: 800 }}>{segmentsCount}</div>
                    </div>
                </div>

                <div style={{ background: 'rgba(255,255,255,0.03)', padding: '1rem', borderRadius: '16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ color: unsyncedCount > 0 ? 'var(--color-warning)' : 'var(--color-success)' }}>
                        {unsyncedCount > 0 ? <UploadCloud size={20} className={isUploading ? "animate-pulse" : ""} /> : <CheckCircle size={20} />}
                    </div>
                    <div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--color-text-dim)', textTransform: 'uppercase', letterSpacing: '1px' }}>Sync Queue</div>
                        <div style={{ fontSize: '1.1rem', fontWeight: 800 }}>{unsyncedCount}</div>
                    </div>
                </div>
            </div>

            <button
                className="btn-premium"
                onClick={toggleRecording}
                style={{
                    width: '100%',
                    justifyContent: 'center',
                    background: isRecording ? 'var(--color-danger)' : 'var(--color-primary)',
                    boxShadow: isRecording ? '0 0 30px rgba(239, 68, 68, 0.3)' : 'var(--shadow-glow)'
                }}
            >
                {isRecording ? <><StopCircle size={20} /> Terminate Recording</> : <><Video size={20} /> Begin AI Monitoring</>}
            </button>

            <style dangerouslySetInnerHTML={{
                __html: `
                @keyframes flash {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.2; }
                }
                .animate-pulse { animation: flash 1.5s infinite; }
            `}} />
        </div>
    );
};

export default DashcamRecorder;
