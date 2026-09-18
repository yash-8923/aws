import React from 'react';
import { LogIn, Shield } from 'lucide-react';

export default function Auth() {
    const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";

    const handleLogin = () => {
        window.location.href = `${BACKEND_URL}/login`;
    };

    return (
        <div className="flex-center" style={{ minHeight: '80vh', padding: '2rem' }}>
            <div className="card-3d reveal" style={{ maxWidth: '420px', width: '100%', textAlign: 'center' }}>
                <div style={{
                    width: '60px',
                    height: '60px',
                    background: 'var(--color-primary-glow)',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 1.5rem',
                    boxShadow: '0 0 20px var(--color-primary-glow)'
                }}>
                    <Shield className="text-primary" size={30} />
                </div>

                <div style={{ marginBottom: '2.5rem' }}>
                    <h2 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Login</h2>
                    <p style={{ color: 'var(--color-text-muted)' }}>Report road damage and help authorities fix issues faster.</p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <button onClick={handleLogin} className="btn-premium" style={{ width: '100%', justifyContent: 'center' }}>
                        <LogIn size={20} />
                        Amazon Cognito Login
                    </button>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', margin: '0.5rem 0' }}>
                        <div style={{ flex: 1, height: '1px', background: 'rgba(255,255,255,0.1)' }}></div>
                        <span style={{ fontSize: '0.8rem', color: 'var(--color-text-dim)' }}>OR</span>
                        <div style={{ flex: 1, height: '1px', background: 'rgba(255,255,255,0.1)' }}></div>
                    </div>

                    <button
                        onClick={() => { window.location.href = `${BACKEND_URL}/login/google`; }}
                        className="btn-premium btn-outline"
                        style={{ width: '100%', justifyContent: 'center' }}
                    >
                        <img
                            src="https://upload.wikimedia.org/wikipedia/commons/c/c1/Google_%22G%22_logo.svg"
                            alt="Google"
                            style={{ width: '18px', height: '18px' }}
                        />
                        Sign in with Google
                    </button>
                </div>

                <p style={{ marginTop: '2rem', fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
                    Don't have an account? Your first login will automatically create one.
                </p>
            </div>
        </div>
    );
}
