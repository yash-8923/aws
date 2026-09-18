import React from 'react';
import DashcamRecorder from '../components/DashcamRecorder';
import { Camera, ShieldCheck } from 'lucide-react';

const DashcamPage = () => {
    return (
        <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
            <div className="card-3d reveal" style={{ textAlign: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
                    <div style={{
                        width: '45px',
                        height: '45px',
                        background: 'rgba(59, 130, 246, 0.1)',
                        borderRadius: '12px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}>
                        <Camera className="text-primary" size={24} />
                    </div>
                    <h2 style={{ fontSize: '2rem' }}>AI Dashcam Mode</h2>
                </div>

                <p style={{ color: 'var(--color-text-muted)', marginBottom: '2.5rem', lineHeight: 1.6 }}>
                    Mount your phone securely. Our AI scans the road in real-time,
                    identifies hazards, and protects privacy by auto-blurring faces.
                </p>

                <div style={{
                    position: 'relative',
                    borderRadius: '24px',
                    overflow: 'hidden',
                    background: '#000',
                    border: '1px solid rgba(255,255,255,0.1)',
                    boxShadow: '0 20px 50px rgba(0,0,0,0.5)'
                }}>
                    <DashcamRecorder />
                </div>

                <div style={{
                    marginTop: '2rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    color: 'var(--color-success)',
                    fontSize: '0.9rem',
                    fontWeight: 600
                }}>
                    <ShieldCheck size={18} /> Privacy Protection Active: Face & Plate Blurring Enabled
                </div>
            </div>
        </div>
    );
};

export default DashcamPage;
