import React, { useEffect, useState } from 'react';
import { Archive, Clock, MapPin, RefreshCw, Loader2 } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";

function normalizeTimestampToMs(value) {
    if (value === null || value === undefined) return null;

    if (typeof value === "number") {
        return value < 1e12 ? value * 1000 : value;
    }

    if (typeof value === "string") {
        const trimmed = value.trim();
        if (/^\d+$/.test(trimmed)) {
            const numeric = Number(trimmed);
            if (!Number.isNaN(numeric)) {
                return numeric < 1e12 ? numeric * 1000 : numeric;
            }
        }

        const parsed = Date.parse(trimmed);
        return Number.isNaN(parsed) ? null : parsed;
    }

    return null;
}

export default function MyReports() {
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const fetchReports = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${BACKEND_URL}/api/reports/me`, {
                credentials: "include"
            });
            if (!res.ok) {
                if (res.status === 401) {
                    setError("Please log in to view your reports.");
                } else {
                    throw new Error(`Server error: ${res.status}`);
                }
                return;
            }
            const data = await res.json();
            setReports(data.reports || []);
        } catch (err) {
            console.error("Failed to load reports from server", err);
            setError("Could not load reports. Please check your connection.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchReports();
    }, []);

    return (
        <div className="card-3d" style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.5rem', background: 'rgba(17,24,39,0.5)', borderBottom: '1px solid rgba(129,140,248,0.1)' }}>
                <h2 style={{ fontSize: '1.25rem', fontWeight: '600', margin: 0 }}>My Reports</h2>
                <button
                    className="btn-premium btn-outline"
                    style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '6px', borderRadius: '8px' }}
                    onClick={fetchReports}
                    disabled={loading}
                    title="Refresh reports"
                >
                    <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
                </button>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem' }}>
                {loading ? (
                    <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--color-text-muted)' }}>
                        <Loader2 size={32} style={{ margin: '0 auto 1rem', animation: 'spin 1s linear infinite' }} />
                        <p>Loading your reports...</p>
                    </div>
                ) : error ? (
                    <div style={{ textAlign: 'center', padding: '2rem 1rem', color: 'var(--color-danger, #ef4444)' }}>
                        <p>{error}</p>
                        <button className="btn-premium" style={{ marginTop: '1rem', fontSize: '0.85rem' }} onClick={fetchReports}>
                            Try Again
                        </button>
                    </div>
                ) : reports.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--color-text-muted)', background: 'rgba(17,24,39,0.4)', borderRadius: '16px', border: '1px dashed rgba(129,140,248,0.2)' }}>
                        <Archive size={48} style={{ opacity: 0.3, margin: '0 auto 1rem', color: 'var(--color-primary)' }} />
                        <p style={{ color: 'var(--color-text-main)', fontWeight: '500' }}>You haven't submitted any reports yet.</p>
                        <p style={{ fontSize: '0.85rem', marginTop: '0.5rem' }}>Reports you submit will appear here across all your devices.</p>
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        {reports.map((report) => {
                            const timestampMs = normalizeTimestampToMs(report.timestamp);
                            const submittedAt = timestampMs ? new Date(timestampMs) : null;

                            const jurisdiction = report.jurisdiction;
                            const portalName =
                                (jurisdiction && typeof jurisdiction === "object" && jurisdiction.portal_name) ? jurisdiction.portal_name :
                                (typeof jurisdiction === "string" ? jurisdiction : null);

                            const locationText =
                                (jurisdiction && typeof jurisdiction === "object" && jurisdiction.ward_district) ? jurisdiction.ward_district :
                                report.ward ||
                                report.sub_area ||
                                report.address ||
                                'Location unavailable';

                            const dateLabel = submittedAt ? submittedAt.toLocaleDateString() : "Unknown date";
                            const timeLabel = submittedAt ? submittedAt.toLocaleTimeString() : "";

                            return (
                            <div key={report.ticketId} className="report-card" style={{
                                background: 'var(--color-surface)',
                                padding: '1.25rem',
                                borderRadius: '12px',
                                border: 'var(--glass-border)',
                                transition: 'var(--transition-normal)'
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                                    <span style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--color-primary)', background: 'rgba(129,140,248,0.1)', padding: '4px 8px', borderRadius: '6px', border: '1px solid rgba(129,140,248,0.2)', letterSpacing: '0.5px' }}>
                                        {report.ticketId}
                                    </span>
                                    <span style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--color-success)', background: 'rgba(52,211,153,0.1)', padding: '4px 8px', borderRadius: '6px', fontWeight: '600' }}>
                                        <Clock size={12} /> {report.status}
                                    </span>
                                </div>

                                <h4 style={{ fontWeight: '600', fontSize: '1.05rem', marginBottom: '0.5rem', color: 'var(--color-text-main)' }}>{portalName || report.damageType || 'Government Portal'}</h4>

                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-text-dim)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                                    <MapPin size={14} className="text-secondary" /> {locationText}
                                </div>

                                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-dim)', borderTop: '1px solid rgba(129,140,248,0.1)', paddingTop: '0.75rem', display: 'flex', justifyContent: 'space-between' }}>
                                    <span>Submitted on {dateLabel}</span>
                                    <span>{timeLabel}</span>
                                </div>
                            </div>
                            );
                        })}
                    </div>
                )}
            </div>

            <style dangerouslySetInnerHTML={{
                __html: `
                @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                .spin { animation: spin 1s linear infinite; }
                .report-card:hover { transform: translateY(-2px); border-color: rgba(129,140,248,0.3) !important; box-shadow: 0 4px 15px rgba(129,140,248,0.1) !important; background: rgba(30,41,59,0.8) !important; }
                `
            }} />
        </div>
    );
}
