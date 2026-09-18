import React from 'react';
import { Link } from 'react-router-dom';
import { Camera, MapPin, ClipboardCheck, ChevronRight } from 'lucide-react';

const StepCard = ({ icon, title, description }) => (
    <div className="reveal step-card" style={{
        flex: '1 1 280px',
        background: 'var(--color-surface)',
        border: '1px solid var(--color-text-dim)',
        borderRadius: '12px',
        padding: '1.75rem',
    }}>
        <div style={{ fontSize: '1.75rem', marginBottom: '1rem' }}>{icon}</div>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--color-text-main)' }}>{title}</h3>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.95rem', lineHeight: 1.6 }}>{description}</p>
    </div>
);

const Home = ({ user }) => {
    return (
        <div style={{ background: 'var(--color-bg)', minHeight: '100vh', color: 'var(--color-text-main)', fontFamily: 'inherit' }}>

            <main style={{ maxWidth: '1200px', margin: '0 auto', padding: '7rem 2rem 4rem' }}>

                {/* Hero */}
                <section style={{ display: 'flex', gap: '3rem', alignItems: 'center', flexWrap: 'wrap', marginBottom: '4rem' }}>
                    <div className="reveal" style={{ flex: '1 1 420px' }}>
                        <h1 style={{ fontSize: 'clamp(2.2rem, 5vw, 3.4rem)', fontWeight: 800, lineHeight: 1.1, marginBottom: '1.25rem', color: 'var(--color-text-main)' }}>
                            Empowering Communities: Fast, Efficient Pothole Reporting.
                        </h1>
                        <p style={{ color: 'var(--color-text-muted)', fontSize: '1.1rem', lineHeight: 1.6, marginBottom: '2rem', maxWidth: '480px' }}>
                            Help improve your local infrastructure. Snap a photo or let your dashcam auto-detect road damage, and track repair status in real-time.
                        </p>
                        <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                            <Link to={user ? "/dashcam" : "/login"} className="cta-btn" style={{
                                background: 'var(--color-accent)', color: '#fff', fontWeight: 700,
                                padding: '0.9rem 1.75rem', borderRadius: '8px', textDecoration: 'none',
                                display: 'inline-flex', alignItems: 'center', gap: '8px'
                            }}>
                                <Camera size={18} /> Report a Pothole
                            </Link>
                            <Link to="/dashboard" className="link-hover" style={{ color: 'var(--color-primary)', fontWeight: 600, textDecoration: 'underline' }}>
                                How it works
                            </Link>
                        </div>
                    </div>
                    <div className="reveal hero-img" style={{ flex: '1 1 420px' }}>
                        <img
                            src="/img.jpg"
                            alt="Road damage reporting"
                            style={{ width: '100%', borderRadius: '12px', border: '1px solid var(--color-text-dim)', display: 'block' }}
                        />
                    </div>
                </section>

                {/* Steps */}
                <section style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginBottom: '2rem' }}>
                    <StepCard
                        icon={<Camera color="var(--color-primary)" size={28} />}
                        title="1. Capture & Locate"
                        description="Snap a photo or let your dashcam auto-detect road damage, tagged with GPS location."
                    />
                    <StepCard
                        icon={<MapPin color="var(--color-accent)" size={28} />}
                        title="2. Submit Your Report"
                        description="Faces and plates are auto-redacted, and severity is flagged to help prioritize repairs."
                    />
                    <StepCard
                        icon={<ClipboardCheck color="var(--color-success)" size={28} />}
                        title="3. Track Progress"
                        description="Your report is routed to the right government portal — stay updated as it's reviewed and fixed."
                    />
                </section>

            </main>

            <footer style={{ borderTop: '1px solid var(--color-text-dim)', background: 'var(--color-surface)', padding: '1.5rem 2rem' }}>
                <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', color: 'var(--color-text-muted)', fontSize: '0.9rem' }}>
                    <div style={{ display: 'flex', gap: '1.5rem' }}>
                        <span>Contact Us</span>
                        <span>Privacy Policy</span>
                    </div>
                    <span>JanSahay Platform</span>
                </div>
            </footer>

            <style dangerouslySetInnerHTML={{
                __html: `
                .cta-btn { transition: transform 0.2s ease, box-shadow 0.2s ease; }
                .cta-btn:hover { transform: scale(1.05); box-shadow: var(--shadow-md); }
                .link-hover { transition: opacity 0.2s ease; }
                .link-hover:hover { opacity: 0.7; }
                .step-card { transition: transform 0.2s ease, box-shadow 0.2s ease; }
                .step-card:hover { transform: translateY(-4px); box-shadow: var(--shadow-md); }
                .hero-img img { transition: transform 0.3s ease; }
                .hero-img:hover img { transform: scale(1.02); }
            `}} />
        </div>
    );
};

export default Home;
