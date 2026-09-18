import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useOnlineStatus } from './hooks/useOnlineStatus';
import { getUnsyncedMedia, markMediaAsSynced, saveMediaLocally } from './utils/db';
import { uploadEvidenceToS3, saveReportToDynamoDB, sendPushNotification } from './services/tracking';

// Components & Pages
import Navbar from './components/Navbar';
import Auth from './components/Auth';
import OnlineIndicator from './components/OnlineIndicator';

// New Pages
import Home from './pages/Home';
import DashcamPage from './pages/DashcamPage';
import MapPage from './pages/MapPage';
import ProfilePage from './pages/ProfilePage';

function App() {
  const isOnline = useOnlineStatus();
  const [captures, setCaptures] = useState([]);
  const [isSyncing, setIsSyncing] = useState(false);
  const [user, setUser] = useState(null);

  const checkSession = async () => {
    const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/me`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setUser({ ...data.user, userData: data.userData, token: data.token });
        return true;
      }
    } catch (err) {
      console.warn("No active session.");
    }
    return false;
  };

  // Sync effect & initial Session Check
  useEffect(() => {
    if (isOnline) {
      syncOfflineData();
    }
    if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
      Notification.requestPermission();
    }
    checkSession();
  }, [isOnline]);

  // Detect OAuth redirect via localStorage flag set by /auth-success.html
  useEffect(() => {
    if (localStorage.getItem('auth_just_completed') === '1') {
      localStorage.removeItem('auth_just_completed');
      checkSession();
    }
  }, []);

  const syncOfflineData = async () => {
    setIsSyncing(true);
    try {
      const unsynced = await getUnsyncedMedia();
      if (unsynced.length > 0) {
        console.log(`Found ${unsynced.length} offline captures to sync`);
        for (const item of unsynced) {
          try {
            const offlineTicketId = `BMC-OFFLINE-${Math.floor(Math.random() * 10000)}`;
            if (item.blob) {
              await uploadEvidenceToS3(item.blob, offlineTicketId);
              const draftData = {
                jurisdiction: item.jurisdiction || 'Unknown',
                damageType: 'Offline Submission',
                severity: 'Unknown'
              };
              await saveReportToDynamoDB(offlineTicketId, draftData, item.id);
              await markMediaAsSynced(item.id);
            } else {
              await markMediaAsSynced(item.id);
            }
          } catch (syncErr) {
            console.error(`Failed to sync capture ${item.id}`, syncErr);
          }
        }
        setCaptures(prev => prev.map(c => ({ ...c, synced: true })));
      }
    } catch (err) {
      console.error("Sync failed", err);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleLogout = async () => {
    const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "";
    try {
      await fetch(`${BACKEND_URL}/api/auth/logout`, { method: "POST", credentials: "include" });
      setUser(null);
    } catch (err) {
      console.error("Logout failed", err);
    }
  };


  // Main UI
  return (
    <Router>
      <div className="app-layout">
        {/* Background Atmosphere */}
        <div className="atmosphere" style={{ zIndex: 0 }}>
          <div className="glow-orb orb-1"></div>
          <div className="glow-orb orb-2"></div>
          <div className="glow-orb orb-3"></div>
        </div>

        <Navbar user={user} onLogout={handleLogout} />

        <main style={{ flex: 1, position: 'relative', zIndex: 1 }}>
          <Routes>
            <Route path="/" element={<Home user={user} />} />

            <Route path="/login" element={
              user ? <Navigate to="/dashboard" /> : <Auth onLogin={setUser} />
            } />

            <Route path="/dashcam" element={
              user ? <DashcamPage /> : <Navigate to="/login" />
            } />

            <Route path="/dashboard" element={
              user ? <MapPage /> : <Navigate to="/login" />
            } />

            <Route path="/profile" element={
              user ? <ProfilePage user={user} /> : <Navigate to="/login" />
            } />

          </Routes>
        </main>

        {/* Persistent Online Indicator */}
        <div className="fixed bottom-4 right-4 z-50">
          <OnlineIndicator />
        </div>
      </div>
    </Router>
  );
}

export default App;
