import React, { useEffect, useState } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { Shield, MapPin, UserCircle, LogOut, Home, Video } from 'lucide-react';

const Navbar = ({ user, onLogout }) => {
    const navigate = useNavigate();
    const location = useLocation();
    const [scrolled, setScrolled] = useState(false);

    useEffect(() => {
        const handleScroll = () => setScrolled(window.scrollY > 20);
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    const handleLogout = () => {
        onLogout();
        navigate('/');
    };

    // Special behavior for Home page transparent nav
    const isHome = location.pathname === '/';

    return (
        <header className={`nav-premium ${scrolled || !isHome ? 'scrolled' : ''}`}>
            <div className="app-container flex-between">
                <NavLink to="/" className="navbar-brand" style={{ transition: '0.3s' }}>
                    <Shield className="text-primary" size={28} />
                    <span className="text-gradient" style={{ fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-1px' }}>
                        JanSahay
                    </span>
                </NavLink>

                <nav style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
                    {user ? (
                        <>
                            <NavLink to="/dashcam" className="nav-link" style={{ color: location.pathname === '/dashcam' ? 'var(--color-primary)' : 'var(--color-text-muted)' }}>
                                <Video size={18} /> <span className="hide-mobile">Dashcam</span>
                            </NavLink>
                            <NavLink to="/dashboard" className="nav-link" style={{ color: location.pathname === '/dashboard' ? 'var(--color-primary)' : 'var(--color-text-muted)' }}>
                                <MapPin size={18} /> <span className="hide-mobile">Intelligence</span>
                            </NavLink>
                            <NavLink to="/profile" className="nav-link" style={{ color: location.pathname === '/profile' ? 'var(--color-primary)' : 'var(--color-text-muted)' }}>
                                <UserCircle size={18} /> <span className="hide-mobile">My Reports</span>
                            </NavLink>
                            <button
                                onClick={handleLogout}
                                className="btn-premium btn-outline"
                                style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}
                            >
                                <LogOut size={16} /> <span className="hide-mobile">Logout</span>
                            </button>
                        </>
                    ) : (
                        <>
                            <NavLink to="/" className="nav-link hide-mobile" style={{ color: location.pathname === '/' ? 'var(--color-primary)' : 'var(--color-text-muted)' }}>
                                <Home size={18} /> Home
                            </NavLink>
                            <NavLink
                                to="/login"
                                className="btn-premium"
                                style={{ padding: '0.6rem 1.5rem', fontSize: '0.9rem' }}
                            >
                                Portal Login
                            </NavLink>
                        </>
                    )}
                </nav>
            </div>

            <style dangerouslySetInnerHTML={{
                __html: `
                .nav-premium {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    z-index: 100;
                    padding: 1rem 0;
                    transition: all 0.3s ease;
                    background: transparent;
                }
                .nav-premium.scrolled {
                    background: rgba(255, 255, 255, 0.85);
                    backdrop-filter: blur(16px);
                    border-bottom: 1px solid rgba(17, 24, 39, 0.08);
                    box-shadow: 0 4px 20px rgba(17, 24, 39, 0.08);
                    padding: 0.6rem 0;
                }
                .navbar-brand {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    text-decoration: none;
                }
                .nav-link {
                    text-decoration: none;
                    font-weight: 500;
                    font-size: 0.9rem;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    transition: all 0.3s ease;
                    color: var(--color-text-muted) !important;
                }
                .nav-link:hover {
                    color: var(--color-primary) !important;
                }
                .nav-link.active {
                    color: var(--color-primary) !important;
                }
                @media (max-width: 600px) {
                    .hide-mobile { display: none; }
                    .text-gradient { font-size: 1.1rem !important; letter-spacing: 0 !important; }
                    .navbar-brand svg { width: 22px !important; height: 22px !important; }
                    .btn-premium { padding: 0.4rem 0.8rem !important; font-size: 0.8rem !important; }
                    .app-container { padding: 0 1rem !important; gap: 8px; }
                }
            `}} />
        </header>
    );
};

export default Navbar;
