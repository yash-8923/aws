import React, { useState, useEffect } from 'react';
import { Loader2, AlertCircle, CheckCircle, Globe, Bot } from 'lucide-react';

export default function AgenticSubmission({ draft, onComplete }) {
    const [step, setStep] = useState(0); // 0: init, 1: nav, 2: fill, 3: captcha, 4: solving, 5: submit, 6: done
    const [captchaInput, setCaptchaInput] = useState('');

    const stepsList = [
        { id: 0, text: "Initializing Amazon Nova Act sandbox..." },
        { id: 1, text: `Navigating to ${draft.jurisdiction}...` },
        { id: 2, text: "Autofilling formal complaint data..." },
        { id: 3, text: "CAPTCHA Intercepted! Human-in-the-loop required." },
        { id: 5, text: "Resuming submission..." },
        { id: 6, text: "Report submitted successfully!" }
    ];

    useEffect(() => {
        let timer;
        if (step === 0) timer = setTimeout(() => setStep(1), 1500);
        else if (step === 1) timer = setTimeout(() => setStep(2), 2000);
        else if (step === 2) timer = setTimeout(() => setStep(3), 2500);
        else if (step === 5) timer = setTimeout(() => setStep(6), 2000);

        return () => clearTimeout(timer);
    }, [step]);

    const handleSolveCaptcha = () => {
        if (captchaInput.trim() === '') return;
        setStep(5);
    };

    return (
        <div className="glass-panel" style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: '1.5rem' }}>
            <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                <Bot size={48} color="var(--color-primary)" style={{ margin: '0 auto 1rem' }} />
                <h2 className="heading-2 text-gradient">Agentic Submission</h2>
                <p style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)' }}>Nova Act is navigating the government portal on your behalf.</p>
            </div>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {stepsList.filter(s => s.id <= step && s.id !== 4).map((s) => (
                    <div key={s.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem', background: 'rgba(255,255,255,0.7)', padding: '1rem', borderRadius: '12px' }}>
                        <div style={{ marginTop: '2px' }}>
                            {step === s.id && s.id !== 3 && s.id !== 6 ? (
                                <Loader2 size={20} className="animate-spin" color="var(--color-primary)" />
                            ) : s.id === 3 && step === 3 ? (
                                <AlertCircle size={20} color="var(--color-warning)" className="animate-pulse" />
                            ) : s.id === 6 ? (
                                <CheckCircle size={20} color="var(--color-success)" />
                            ) : (
                                <CheckCircle size={20} color="var(--color-text-muted)" />
                            )}
                        </div>
                        <div style={{ flex: 1 }}>
                            <p style={{ fontWeight: '500', color: step === s.id && s.id !== 6 ? 'var(--color-primary)' : 'var(--color-text-main)' }}>{s.text}</p>
                        </div>
                    </div>
                ))}

                {step === 3 && (
                    <div style={{ background: 'var(--color-surface)', border: '2px solid var(--color-warning)', padding: '1.5rem', borderRadius: '16px', marginTop: '1rem', boxShadow: '0 10px 25px -5px rgba(245, 158, 11, 0.2)' }}>
                        <h3 style={{ fontSize: '1rem', fontWeight: '700', color: 'var(--color-warning)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Globe size={18} /> Solve CAPTCHA to Continue
                        </h3>

                        <div style={{ background: '#f0f0f0', padding: '1rem', borderRadius: '8px', textAlign: 'center', letterSpacing: '8px', fontSize: '1.5rem', fontWeight: '800', fontFamily: 'monospace', textDecoration: 'line-through', marginBottom: '1rem' }}>
                            XR89PQ
                        </div>

                        <div className="input-group">
                            <input
                                className="input-field"
                                placeholder="Enter characters exactly"
                                value={captchaInput}
                                onChange={e => setCaptchaInput(e.target.value)}
                                autoFocus
                            />
                        </div>

                        <button className="btn btn-primary" style={{ width: '100%', background: 'var(--color-warning)' }} onClick={handleSolveCaptcha}>
                            Submit to Portal & Resume
                        </button>
                    </div>
                )}

                {step === 6 && (
                    <div style={{ marginTop: '2rem', textAlign: 'center' }}>
                        <div style={{ background: 'rgba(16, 185, 129, 0.1)', color: 'var(--color-success)', padding: '1.5rem', borderRadius: '16px', marginBottom: '1.5rem' }}>
                            <h3 style={{ fontSize: '1.5rem', fontWeight: '800', marginBottom: '0.5rem' }}>Success!</h3>
                            <p>Your ticket ID is: <strong>BMC-2026-9938X</strong></p>
                        </div>
                        <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => onComplete("BMC-2026-9938X")}>
                            Finish & Track Status
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
