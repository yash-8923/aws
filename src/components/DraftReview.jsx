import React, { useState, useEffect } from 'react';
import { mockGenerateDraft } from '../services/draft';
import { Loader2, ArrowLeft, Send } from 'lucide-react';

export default function DraftReview({ capture, onClose, onSubmit }) {
    const [draft, setDraft] = useState(null);
    const [isGenerating, setIsGenerating] = useState(true);

    useEffect(() => {
        async function fetchDraft() {
            try {
                const generatedDraft = await mockGenerateDraft(capture);
                setDraft(generatedDraft);
            } catch (err) {
                console.error("Draft generation failed", err);
            } finally {
                setIsGenerating(false);
            }
        }
        fetchDraft();
    }, [capture]);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setDraft(prev => ({ ...prev, [name]: value }));
    };

    if (isGenerating) {
        return (
            <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
                <Loader2 size={48} className="animate-spin" color="var(--color-primary)" style={{ marginBottom: '1rem' }} />
                <h2 className="heading-2">Drafting Application...</h2>
                <p style={{ color: 'var(--color-text-muted)' }}>Amazon Bedrock is compiling your evidence into a formal complaint.</p>
            </div>
        );
    }

    if (!draft) {
        return (
            <div className="glass-panel" style={{ padding: '2rem', textAlign: 'center' }}>
                <p>Failed to generate draft.</p>
                <button className="btn btn-secondary" onClick={onClose}>Go Back</button>
            </div>
        );
    }

    return (
        <div className="glass-panel" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem', borderBottom: '1px solid rgba(0,0,0,0.05)' }}>
                <button onClick={onClose} style={{ background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                    <ArrowLeft size={24} color="var(--color-text-main)" />
                </button>
                <h2 className="heading-2" style={{ fontSize: '1.25rem', margin: 0 }}>Review Application</h2>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem' }}>
                <p style={{ marginBottom: '1.5rem', fontSize: '0.9rem', color: 'var(--color-text-muted)' }}>
                    Please review the auto-generated details below. You can edit any field before final submission.
                </p>

                <div className="input-group">
                    <label className="input-label">Jurisdiction (Auto-Mapped)</label>
                    <input className="input-field" disabled value={`${draft.jurisdiction} - ${draft.ward}`} />
                </div>

                <div className="input-group">
                    <label className="input-label">Issue Type</label>
                    <input className="input-field" name="damageType" value={draft.damageType} onChange={handleChange} />
                </div>

                <div className="input-group">
                    <label className="input-label">Severity</label>
                    <select className="input-field" name="severity" value={draft.severity} onChange={handleChange} style={{ appearance: 'none' }}>
                        <option value="Low">Low</option>
                        <option value="Medium">Medium</option>
                        <option value="High">High</option>
                        <option value="Critical">Critical</option>
                    </select>
                </div>

                <div className="input-group">
                    <label className="input-label">Detailed Description</label>
                    <textarea
                        className="input-field"
                        name="description"
                        value={draft.description}
                        onChange={handleChange}
                        rows={6}
                        style={{ resize: 'vertical' }}
                    />
                </div>

                <div className="input-group">
                    <label className="input-label">Applicant Name</label>
                    <input className="input-field" name="applicantName" value={draft.applicantName} onChange={handleChange} />
                </div>

                <div className="input-group">
                    <label className="input-label">Phone Number</label>
                    <input className="input-field" name="phoneNumber" value={draft.phoneNumber} onChange={handleChange} />
                </div>
            </div>

            <div style={{ padding: '1rem', borderTop: '1px solid rgba(0,0,0,0.05)', background: 'rgba(255,255,255,0.8)' }}>
                <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => onSubmit(draft)}>
                    <Send size={20} />
                    Confirm & Submit Request
                </button>
            </div>
        </div>
    );
}
