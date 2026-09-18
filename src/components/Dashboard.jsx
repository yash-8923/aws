import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { FileText, AlertTriangle, ShieldCheck, MapPin, ExternalLink, Globe, CheckCircle, Video, Image as ImageIcon, Download } from 'lucide-react';

// Fix for default Leaflet marker icons in React
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

const getSeverityColor = (severity) => {
    switch (severity?.toLowerCase()) {
        case 'severe': return 'var(--color-danger)';
        case 'moderate': return 'var(--color-warning)';
        default: return 'var(--color-success)';
    }
};

// Helper component to fly map to selected cluster or first cluster on load
const MapFlyTo = ({ cluster, clusters }) => {
    const map = useMap();
    const [hasInitialFly, setHasInitialFly] = React.useState(false);

    useEffect(() => {
        if (cluster) {
            map.flyTo([cluster.latitude, cluster.longitude], 14, { duration: 1 });
        }
    }, [cluster, map]);

    useEffect(() => {
        if (!hasInitialFly && clusters.length > 0) {
            map.flyTo([clusters[0].latitude, clusters[0].longitude], 13, { duration: 1.5 });
            setHasInitialFly(true);
        }
    }, [clusters, hasInitialFly, map]);

    return null;
};

const Dashboard = () => {
    const [clusters, setClusters] = useState([]);
    const [selectedCluster, setSelectedCluster] = useState(null);
    const [draftRequestStatus, setDraftRequestStatus] = useState('idle');
    const [markFiledStatus, setMarkFiledStatus] = useState('idle');
    const [generatedDraft, setGeneratedDraft] = useState(null);
    const [totalEvents, setTotalEvents] = useState(0);

    useEffect(() => {
        fetchClusters();
        // Auto-refresh every 15 seconds to pick up newly processed events
        const interval = setInterval(fetchClusters, 15000);
        return () => clearInterval(interval);
    }, []);

    const fetchClusters = async () => {
        try {
            const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";
            const res = await fetch(`${BACKEND_URL}/api/clusters`, { credentials: 'include' });
            const data = await res.json();
            setClusters(data.clusters || []);
            // Count total events across clusters
            const total = (data.clusters || []).reduce((sum, c) => sum + c.event_count, 0);
            setTotalEvents(total);
        } catch (error) {
            console.error("Failed to fetch clusters:", error);
        }
    };

    const handleGenerateComplaint = async () => {
        if (!selectedCluster) return;

        setDraftRequestStatus('generating');
        try {
            const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";
            const res = await fetch(`${BACKEND_URL}/api/reports/generate_complaint`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(selectedCluster),
                credentials: 'include'
            });
            const data = await res.json();
            if (res.ok) {
                setGeneratedDraft(data);
                setDraftRequestStatus('done');
            } else {
                setDraftRequestStatus('idle');
                alert("Failed to compile damage report: " + JSON.stringify(data));
            }
        } catch (error) {
            console.error("Draft generation failed", error);
            setDraftRequestStatus('idle');
            alert("Connection error during draft generation.");
        }
    };

    const handleMarkFiled = async () => {
        if (!selectedCluster) return;
        setMarkFiledStatus('marking');
        try {
            const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";
            const res = await fetch(`${BACKEND_URL}/api/clusters/mark_filed`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(selectedCluster),
                credentials: 'include'
            });
            if (res.ok) {
                setMarkFiledStatus('success');
                setTimeout(() => {
                    setSelectedCluster(null);
                    setGeneratedDraft(null);
                    setMarkFiledStatus('idle');
                    fetchClusters(); // refresh map
                }, 1500);
            } else {
                setMarkFiledStatus('idle');
                alert("Failed to mark as filed");
            }
        } catch (error) {
            console.error("Filing error:", error);
            setMarkFiledStatus('idle');
            alert("Error trying to mark complaint as filed.");
        }
    };

    // Group clusters by portal for the sidebar summary
    const portalGroups = {};
    clusters.forEach(c => {
        const key = c.portal_url || 'unknown';
        if (!portalGroups[key]) {
            portalGroups[key] = { portal_name: c.portal_name, portal_url: c.portal_url, clusters: [] };
        }
        portalGroups[key].clusters.push(c);
    });

    return (
        <div className="dashboard-root">
            {/* Header Stats */}
            <div className="dashboard-header">
                <h2 className="heading-3 dashboard-title">Damage Intelligence Map</h2>
                <p className="dashboard-subtitle">
                    Real-time AI insights from crowdsourced dashcams.
                </p>
                {clusters.length > 0 && (
                    <div className="dashboard-stats">
                        <div className="dashboard-stat-chip" style={{ background: 'rgba(59,130,246,0.1)' }}>
                            <strong style={{ color: 'var(--color-primary)' }}>{totalEvents}</strong> events detected
                        </div>
                        <div className="dashboard-stat-chip" style={{ background: 'rgba(139,92,246,0.1)' }}>
                            <strong style={{ color: 'var(--color-secondary)' }}>{clusters.length}</strong> clusters
                        </div>
                        <div className="dashboard-stat-chip" style={{ background: 'rgba(16,185,129,0.1)' }}>
                            <strong style={{ color: 'var(--color-success)' }}>{Object.keys(portalGroups).length}</strong> portals
                        </div>
                    </div>
                )}
                {clusters.length === 0 && (
                    <div className="dashboard-empty-state">
                        No pothole events detected yet. Start the dashcam to begin recording and detecting road damage.
                    </div>
                )}
            </div>

            {/* Portal Groups Summary (horizontal scrollable) */}
            {Object.keys(portalGroups).length > 0 && (
                <div className="portal-groups-scroll">
                    {Object.values(portalGroups).map((group, idx) => (
                        <button key={idx}
                            type="button"
                            onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                console.log('Portal clicked:', group.portal_name);
                                setSelectedCluster(group.clusters[0]);
                                setGeneratedDraft(null);
                                setDraftRequestStatus('idle');
                            }}
                            className={`portal-group-btn ${selectedCluster && selectedCluster.portal_name === group.portal_name ? 'portal-group-btn--active' : ''}`}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontWeight: '700', marginBottom: '4px' }}>
                                <Globe size={14} />
                                {group.portal_name}
                            </div>
                            <div style={{ color: 'var(--color-text-muted)' }}>
                                {group.clusters.length} sub-area{group.clusters.length !== 1 ? 's' : ''} •{' '}
                                {group.clusters.reduce((s, c) => s + c.event_count, 0)} events
                            </div>
                        </button>
                    ))}
                </div>
            )}

            {/* Map */}
            <div className="dashboard-map-container">
                <MapContainer
                    center={clusters.length > 0 ? [clusters[0].latitude, clusters[0].longitude] : [26.85, 80.95]}
                    zoom={13}
                    minZoom={2}
                    maxBounds={[
                        [-85, -180],
                        [85, 180],
                    ]}
                    maxBoundsViscosity={0.7}
                    style={{ height: '100%', width: '100%' }}
                >
                    <MapFlyTo cluster={selectedCluster} clusters={clusters} />
                    <TileLayer
                        url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                        noWrap
                    />

                    {clusters.map((cluster) => {
                        const customMarker = L.divIcon({
                            className: 'custom-marker',
                            html: `<div style="background-color: ${getSeverityColor(cluster.severity)}; width: 24px; height: 24px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 10px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; color: white; font-size: 10px; font-weight: bold;">${cluster.event_count}</div>`,
                            iconSize: [24, 24],
                            iconAnchor: [12, 12]
                        });

                        return (
                            <Marker
                                key={cluster.cluster_id}
                                position={[cluster.latitude, cluster.longitude]}
                                icon={customMarker}
                                eventHandlers={{
                                    click: () => {
                                        setSelectedCluster(cluster);
                                        setGeneratedDraft(null);
                                        setDraftRequestStatus('idle');
                                    }
                                }}
                            >
                                <Popup>
                                    <div style={{ padding: '4px', textAlign: 'center', minWidth: '140px' }}>
                                        <b style={{ textTransform: 'capitalize', color: getSeverityColor(cluster.severity) }}>
                                            {cluster.severity} Damage
                                        </b><br />
                                        <span style={{ fontSize: '0.8rem' }}>{cluster.sub_area || cluster.road_name}</span><br />
                                        <span style={{ fontSize: '0.75rem', color: '#666' }}>
                                            {cluster.event_count} reports • {cluster.portal_name}
                                        </span>
                                    </div>
                                </Popup>
                            </Marker>
                        );
                    })}
                </MapContainer>
            </div>

            {/* Cluster Details Panel */}
            {selectedCluster && (
                <div className="glass-panel cluster-details-panel">
                    <div className="cluster-details-header">
                        <div style={{ paddingRight: '1rem', minWidth: 0, flex: 1 }}>
                            <h3 className="cluster-title">
                                <MapPin size={18} />
                                {selectedCluster.sub_area || selectedCluster.road_name}
                            </h3>
                            <p className="cluster-subtitle">
                                Hotspot ID: {selectedCluster.cluster_id.split('_')[1]}
                            </p>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px', flexShrink: 0 }}>
                            <button
                                onClick={() => setSelectedCluster(null)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-primary)', fontSize: '0.8rem', fontWeight: 'bold' }}>
                                ✕ Close
                            </button>
                            <span style={{
                                background: getSeverityColor(selectedCluster.severity),
                                color: 'white',
                                padding: '4px 10px',
                                borderRadius: '20px',
                                fontSize: '0.75rem',
                                fontWeight: 'bold',
                                textTransform: 'uppercase'
                            }}>
                                {selectedCluster.severity}
                            </span>
                        </div>
                    </div>

                    {/* Portal Info */}
                    <div className="portal-info-bar">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0, flex: 1 }}>
                            <Globe size={16} style={{ color: 'var(--color-primary)', flexShrink: 0 }} />
                            <div style={{ minWidth: 0 }}>
                                <p style={{ margin: 0, fontSize: '0.8rem', fontWeight: '700', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{selectedCluster.portal_name}</p>
                                <p style={{ margin: 0, fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>Filing Portal</p>
                            </div>
                        </div>
                        {selectedCluster.portal_url && (
                            <a
                                href={selectedCluster.portal_url}
                                target="_blank"
                                rel="noreferrer"
                                className="portal-open-link"
                            >
                                <ExternalLink size={12} /> Open Portal
                            </a>
                        )}
                    </div>

                    {/* Stats and Evidence */}
                    <div className="stats-evidence-section">
                        <div style={{ display: 'flex', gap: '1rem', borderBottom: '1px solid rgba(0,0,0,0.05)', paddingBottom: '0.75rem' }}>
                            <div style={{ flex: 1 }}>
                                <p style={{ margin: '0 0 4px 0', fontSize: '0.85rem', fontWeight: '600' }}>Aggregated Reports</p>
                                <p style={{ margin: 0, fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--color-primary)', lineHeight: '1' }}>{selectedCluster.event_count}</p>
                            </div>
                        </div>

                        <div>
                            <p style={{ margin: 0, fontSize: '0.8rem', fontWeight: '600', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                                <ShieldCheck size={14} /> Evidence Artifacts
                            </p>
                            <div className="evidence-scroll">
                                {selectedCluster.representative_clip && (
                                    <div className="evidence-card">
                                        <div className="evidence-thumb">
                                            <Video size={24} color="#64748b" />
                                        </div>
                                        <a href={selectedCluster.representative_clip} download target="_blank" rel="noreferrer" className="evidence-download-btn" style={{ background: 'var(--color-primary)' }}>
                                            <Download size={10} style={{ marginRight: '2px' }} /> Clip
                                        </a>
                                    </div>
                                )}
                                {selectedCluster.best_images && selectedCluster.best_images.map((imgUrl, i) => (
                                    <div key={i} className="evidence-card">
                                        <div className="evidence-thumb" style={{ backgroundImage: `url(${imgUrl})`, backgroundSize: 'cover', backgroundPosition: 'center' }} />
                                        <a href={imgUrl} download target="_blank" rel="noreferrer" className="evidence-download-btn" style={{ background: 'var(--color-success)' }}>
                                            <Download size={10} style={{ marginRight: '2px' }} /> Frame {i + 1}
                                        </a>
                                    </div>
                                ))}
                                {!selectedCluster.representative_clip && (!selectedCluster.best_images || selectedCluster.best_images.length === 0) && (
                                    <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>No artifacts available</span>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Individual Events List */}
                    {selectedCluster.events && selectedCluster.events.length > 0 && (
                        <div style={{ marginTop: '1rem' }}>
                            <p style={{ margin: '0 0 8px', fontSize: '0.85rem', fontWeight: '600' }}>Event Details ({selectedCluster.events.length})</p>
                            <div className="events-list">
                                {selectedCluster.events.map((ev, idx) => (
                                    <div key={ev.event_id || idx} className="event-row">
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0, flex: 1 }}>
                                            <span style={{
                                                width: '8px', height: '8px', borderRadius: '50%',
                                                background: getSeverityColor(ev.severity), flexShrink: 0
                                            }} />
                                            <span className="event-address">
                                                {ev.address ? ev.address.substring(0, 40) + (ev.address.length > 40 ? '...' : '') : `GPS: ${ev.lat}, ${ev.lng}`}
                                            </span>
                                        </div>
                                        <span className="event-severity" style={{ color: getSeverityColor(ev.severity) }}>
                                            {ev.severity} ({(ev.confidence * 100).toFixed(0)}%)
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Generate Complaint Button */}
                    {!generatedDraft ? (
                        <button
                            className="btn btn-primary"
                            style={{ width: '100%', marginTop: '1rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}
                            onClick={handleGenerateComplaint}
                            disabled={draftRequestStatus === 'generating'}
                        >
                            {draftRequestStatus === 'generating' ? (
                                <>Processing with Bedrock Nova Pro...</>
                            ) : (
                                <><FileText size={18} /> Auto-Draft Complaint</>
                            )}
                        </button>
                    ) : (
                        <div className="draft-result-panel">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-success)', marginBottom: '0.5rem' }}>
                                <ShieldCheck size={18} />
                                <span style={{ fontWeight: '600', fontSize: '0.9rem' }}>Draft Ready for {generatedDraft.suggested_authority}</span>
                            </div>
                            <pre className="draft-text">
                                {generatedDraft.generated_draft}
                            </pre>
                            <div className="draft-actions">
                                {selectedCluster.portal_url && (
                                    <a
                                        href={selectedCluster.portal_url}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="btn btn-primary draft-action-btn"
                                    >
                                        <ExternalLink size={16} /> Open Portal
                                    </a>
                                )}
                                <button
                                    className="btn btn-success draft-action-btn"
                                    onClick={handleMarkFiled}
                                    disabled={markFiledStatus !== 'idle'}
                                >
                                    {markFiledStatus === 'marking' ? 'Marking...' : markFiledStatus === 'success' ? 'Filed!' : <><CheckCircle size={16} /> Mark as Filed</>}
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}

            <style dangerouslySetInnerHTML={{
                __html: `
                @keyframes slideUp {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                .leaflet-container {
                    z-index: 1;
                    background: #aad3df;
                }

                /* Dashboard Root */
                .dashboard-root {
                    display: flex;
                    flex-direction: column;
                    height: 100%;
                    gap: 0.75rem;
                    overflow-y: auto;
                    padding-bottom: 2rem;
                }

                /* Header */
                .dashboard-header {
                    padding: 0 1rem;
                }
                .dashboard-title {
                    margin-bottom: 0.2rem;
                }
                .dashboard-subtitle {
                    font-size: 0.85rem;
                    color: var(--color-text-muted);
                    margin: 0;
                }
                .dashboard-stats {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 0.5rem;
                    margin-top: 0.5rem;
                }
                .dashboard-stat-chip {
                    padding: 6px 12px;
                    border-radius: 8px;
                    font-size: 0.8rem;
                }
                .dashboard-empty-state {
                    background: rgba(0,0,0,0.03);
                    padding: 1rem;
                    border-radius: 8px;
                    margin-top: 0.5rem;
                    text-align: center;
                    font-size: 0.85rem;
                    color: var(--color-text-muted);
                }

                /* Portal Groups */
                .portal-groups-scroll {
                    padding: 0 1rem;
                    overflow-x: auto;
                    display: flex;
                    gap: 0.5rem;
                    position: relative;
                    z-index: 20;
                    -webkit-overflow-scrolling: touch;
                }
                .portal-group-btn {
                    min-width: 180px;
                    background: linear-gradient(135deg, rgba(59,130,246,0.08), rgba(139,92,246,0.08));
                    padding: 8px 12px;
                    border-radius: 10px;
                    border: 1px solid rgba(59,130,246,0.15);
                    font-size: 0.78rem;
                    flex-shrink: 0;
                    cursor: pointer;
                    transition: all 0.2s;
                    user-select: none;
                    text-align: left;
                    color: inherit;
                    font-family: inherit;
                }
                .portal-group-btn--active {
                    background: linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.15));
                    border: 2px solid var(--color-primary);
                }

                /* Map */
                .dashboard-map-container {
                    min-height: 350px;
                    height: 50vh;
                    flex-shrink: 0;
                    position: relative;
                    border-radius: 12px;
                    overflow: hidden;
                    margin: 0 1rem;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                }

                /* Cluster Details Panel */
                .cluster-details-panel {
                    margin: 0 1rem 1rem;
                    padding: 1rem;
                    animation: slideUp 0.3s ease-out;
                    position: relative;
                }
                .cluster-details-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                }
                .cluster-title {
                    margin: 0;
                    font-size: 1.1rem;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                }
                .cluster-subtitle {
                    margin: 4px 0 0;
                    font-size: 0.85rem;
                    color: var(--color-text-muted);
                }

                /* Portal Info Bar */
                .portal-info-bar {
                    margin-top: 0.75rem;
                    padding: 8px 12px;
                    background: linear-gradient(135deg, rgba(59,130,246,0.08), rgba(139,92,246,0.05));
                    border-radius: 8px;
                    border: 1px solid rgba(59,130,246,0.15);
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 8px;
                }
                .portal-open-link {
                    display: inline-flex;
                    align-items: center;
                    gap: 4px;
                    font-size: 0.75rem;
                    color: var(--color-primary);
                    text-decoration: none;
                    padding: 4px 8px;
                    background: white;
                    border-radius: 6px;
                    border: 1px solid rgba(59,130,246,0.2);
                    white-space: nowrap;
                    flex-shrink: 0;
                }

                /* Stats & Evidence */
                .stats-evidence-section {
                    margin-top: 0.75rem;
                    display: flex;
                    flex-direction: column;
                    gap: 0.75rem;
                    background: rgba(0,0,0,0.02);
                    padding: 1rem;
                    border-radius: 8px;
                }
                .evidence-scroll {
                    display: flex;
                    gap: 8px;
                    overflow-x: auto;
                    padding-bottom: 4px;
                    -webkit-overflow-scrolling: touch;
                }
                .evidence-card {
                    flex-shrink: 0;
                    width: 100px;
                    background: #fff;
                    border-radius: 8px;
                    overflow: hidden;
                    border: 1px solid rgba(0,0,0,0.1);
                }
                .evidence-thumb {
                    height: 70px;
                    background: #e2e8f0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .evidence-download-btn {
                    display: block;
                    padding: 4px;
                    text-align: center;
                    font-size: 0.7rem;
                    text-decoration: none;
                    color: white;
                    font-weight: bold;
                }

                /* Events List */
                .events-list {
                    overflow-y: auto;
                    display: flex;
                    flex-direction: column;
                    gap: 6px;
                }
                .event-row {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    padding: 6px 8px;
                    border-radius: 6px;
                    background: rgba(0,0,0,0.02);
                    border: 1px solid rgba(0,0,0,0.05);
                    font-size: 0.75rem;
                    gap: 8px;
                }
                .event-address {
                    color: var(--color-text-muted);
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }
                .event-severity {
                    font-weight: 600;
                    text-transform: capitalize;
                    white-space: nowrap;
                    flex-shrink: 0;
                }

                /* Draft Result */
                .draft-result-panel {
                    margin-top: 1rem;
                    padding: 1rem;
                    background: var(--color-bg);
                    border-radius: 8px;
                    border: 1px solid rgba(0,0,0,0.1);
                }
                .draft-text {
                    white-space: pre-wrap;
                    font-family: inherit;
                    font-size: 0.85rem;
                    color: var(--color-text-main);
                    margin: 0;
                    max-height: 150px;
                    overflow-y: auto;
                    padding: 0.5rem;
                    background: rgba(255, 255, 255, 0.05);
                    border-radius: 4px;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }
                .draft-actions {
                    display: flex;
                    gap: 8px;
                    margin-top: 0.5rem;
                }
                .draft-action-btn {
                    flex: 1;
                    padding: 0.5rem;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    gap: 6px;
                    text-decoration: none;
                }

                /* ===== MOBILE RESPONSIVE ===== */
                @media (max-width: 768px) {
                    .dashboard-root {
                        gap: 0.5rem;
                        padding-bottom: 1.5rem;
                    }
                    .dashboard-header {
                        padding: 0 0.5rem;
                    }
                    .dashboard-title {
                        font-size: 1rem !important;
                    }
                    .dashboard-subtitle {
                        font-size: 0.75rem;
                    }
                    .dashboard-stat-chip {
                        padding: 4px 8px;
                        font-size: 0.72rem;
                    }
                    .dashboard-empty-state {
                        padding: 0.75rem;
                        font-size: 0.78rem;
                    }

                    /* Portal scroll cards */
                    .portal-groups-scroll {
                        padding: 0 0.5rem;
                        gap: 0.4rem;
                    }
                    .portal-group-btn {
                        min-width: 150px;
                        padding: 6px 10px;
                        font-size: 0.72rem;
                    }

                    /* Map - shorter on mobile */
                    .dashboard-map-container {
                        min-height: 220px;
                        height: 35vh;
                        margin: 0 0.5rem;
                        border-radius: 10px;
                    }

                    /* Cluster details */
                    .cluster-details-panel {
                        margin: 0 0.5rem 0.75rem;
                        padding: 0.75rem;
                    }
                    .cluster-details-header {
                        flex-direction: column;
                        gap: 8px;
                    }
                    .cluster-details-header > div:last-child {
                        flex-direction: row;
                        align-items: center;
                        justify-content: space-between;
                        width: 100%;
                    }
                    .cluster-title {
                        font-size: 0.95rem;
                    }
                    .cluster-subtitle {
                        font-size: 0.75rem;
                    }

                    /* Portal info */
                    .portal-info-bar {
                        flex-direction: column;
                        align-items: stretch;
                        gap: 6px;
                        padding: 8px 10px;
                    }
                    .portal-open-link {
                        align-self: flex-start;
                    }

                    /* Stats & Evidence */
                    .stats-evidence-section {
                        padding: 0.75rem;
                    }
                    .evidence-card {
                        width: 85px;
                    }
                    .evidence-thumb {
                        height: 55px;
                    }

                    /* Events */
                    .event-row {
                        flex-direction: column;
                        align-items: flex-start;
                        gap: 2px;
                        padding: 8px;
                    }
                    .event-address {
                        white-space: normal;
                        word-break: break-word;
                    }

                    /* Draft */
                    .draft-result-panel {
                        padding: 0.75rem;
                    }
                    .draft-text {
                        font-size: 0.78rem;
                        max-height: 120px;
                    }
                    .draft-actions {
                        flex-direction: column;
                    }
                    .draft-action-btn {
                        width: 100%;
                    }
                }

                /* Small phones */
                @media (max-width: 400px) {
                    .dashboard-map-container {
                        min-height: 180px;
                        height: 30vh;
                    }
                    .portal-group-btn {
                        min-width: 130px;
                        font-size: 0.68rem;
                    }
                    .dashboard-stats {
                        gap: 0.3rem;
                    }
                    .dashboard-stat-chip {
                        padding: 3px 6px;
                        font-size: 0.68rem;
                    }
                }
                `
            }} />
        </div>
    );
};

export default Dashboard;
