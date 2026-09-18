import React, { useState, useRef } from 'react';
import { Mic, Square, Loader2 } from 'lucide-react';

export default function AudioRecorder({ onRecordingComplete }) {
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorderRef.current = new MediaRecorder(stream);
            audioChunksRef.current = [];

            mediaRecorderRef.current.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };

            mediaRecorderRef.current.onstop = () => {
                setIsProcessing(true);
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                // Stop all tracks to release the microphone
                stream.getTracks().forEach(track => track.stop());

                onRecordingComplete(audioBlob);
                setIsProcessing(false);
            };

            mediaRecorderRef.current.start();
            setIsRecording(true);
        } catch (err) {
            console.error('Error accessing microphone', err);
            alert('Could not access microphone. Please check permissions.');
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        }
    };

    if (isProcessing) {
        return (
            <button className="btn btn-secondary" disabled style={{ width: '100%' }}>
                <Loader2 className="animate-spin" size={20} />
                Processing Audio...
            </button>
        );
    }

    if (isRecording) {
        return (
            <button
                className="btn"
                style={{
                    width: '100%',
                    backgroundColor: 'var(--color-danger)',
                    color: 'white',
                    animation: 'pulse 1.5s infinite'
                }}
                onClick={stopRecording}
            >
                <Square size={20} fill="currentColor" />
                Stop Recording
            </button>
        );
    }

    return (
        <button className="btn btn-primary" style={{ width: '100%' }} onClick={startRecording}>
            <Mic size={20} />
            Record Voice Note
        </button>
    );
}
