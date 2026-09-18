import React from 'react';
import MyReports from '../components/MyReports';
import { User, Calendar, Shield } from 'lucide-react';

const ProfilePage = ({ user }) => {
    const memberSince = user?.created_at
        ? new Date(parseInt(user.created_at) * 1000).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })
        : "March 2026";

    const displayName = user?.userData?.name || user?.name || (user?.email ? user.email.split('@')[0] : "Citizen Reporter");

    return (
        <div className="app-container" style={{ padding: '4rem 2rem', maxWidth: '1200px', margin: '0 auto', minHeight: 'calc(100vh - 80px)' }}>

            <div style={{ marginBottom: '3rem' }}>
                <h1 style={{ fontSize: '2.5rem', fontWeight: 700, letterSpacing: '-0.02em', marginBottom: '0.5rem' }}>Your Profile</h1>
                <p style={{ color: 'var(--color-text-muted)', fontSize: '1.1rem' }}>Manage your civic identity and monitor active reports.</p>
            </div>

            <div className="profile-grid">

                {/* Profile Card */}
                <div className="card-3d reveal" style={{ height: 'fit-content' }}>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{
                            width: '80px',
                            height: '80px',
                            borderRadius: '50%',
                            margin: '0 auto 1.5rem',
                            background: 'var(--gradient-primary)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '2rem',
                            fontWeight: 'bold',
                            boxShadow: '0 0 30px var(--color-primary-glow)'
                        }}>
                            { displayName !== "Citizen Reporter" ? displayName.charAt(0).toUpperCase() : <User size={40} />}
                        </div>

                        <h2 style={{ fontSize: '1.75rem', marginBottom: '0.25rem' }}>{displayName}</h2>
                        <p style={{ color: 'var(--color-text-muted)', marginBottom: '1.5rem' }}>{user?.email}</p>

                        <div style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '8px',
                            padding: '0.5rem 1rem',
                            background: 'rgba(255,255,255,0.05)',
                            borderRadius: '100px',
                            fontSize: '0.85rem'
                        }}>
                            <Calendar size={14} className="text-primary" /> Member Since {memberSince}
                        </div>
                    </div>

                    <div style={{ marginTop: '2.5rem', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '2rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '1rem' }}>
                            <Shield className="text-success" size={20} />
                            <div>
                                <h4 style={{ fontSize: '0.9rem' }}>Civic Identity Verified</h4>
                                <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Your reports are prioritized for review.</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Reports History */}
                <div style={{ minHeight: '500px', display: 'flex', flexDirection: 'column' }}>
                    <div className="reveal delay-1" style={{ flex: 1, height: '100%' }}>
                        <MyReports />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ProfilePage;
