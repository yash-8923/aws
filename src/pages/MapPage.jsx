import React from 'react';
import Dashboard from '../components/Dashboard';

const MapPage = () => {
    return (
        <div className="map-page-wrapper">
            <div className="card-3d reveal map-page-card">
                <div className="map-page-header">
                    <h2 style={{ fontSize: '1.3rem', margin: 0 }}>Intelligence Map</h2>
                    <p style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem', margin: '0.25rem 0 0' }}>Real-time road hazard detection across the city</p>
                </div>
                <div style={{ flex: 1, minHeight: 0 }}>
                    <Dashboard />
                </div>
            </div>

            <style dangerouslySetInnerHTML={{
                __html: `
                .map-page-wrapper {
                    padding: 1rem;
                    padding-top: 5rem;
                    min-height: calc(100vh - 5rem);
                    display: flex;
                    flex-direction: column;
                }
                .map-page-card {
                    flex: 1;
                    padding: 0;
                    overflow: visible;
                    display: flex;
                    flex-direction: column;
                    min-height: 0;
                }
                .map-page-header {
                    padding: 1rem 1.5rem;
                    border-bottom: 1px solid rgba(255,255,255,0.05);
                }
                @media (max-width: 768px) {
                    .map-page-wrapper {
                        padding: 0.5rem;
                        padding-top: 4rem;
                        min-height: calc(100vh - 4rem);
                    }
                    .map-page-header {
                        padding: 0.75rem 1rem;
                    }
                    .map-page-header h2 {
                        font-size: 1.1rem !important;
                    }
                    .map-page-header p {
                        font-size: 0.75rem !important;
                    }
                }
            `}} />
        </div>
    );
};

export default MapPage;
