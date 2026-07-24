import React, { useEffect, useState } from 'react';
import { FileText, Download } from 'lucide-react';

export default function SarReportView() {
  const [sar, setSar] = useState(null);

  useEffect(() => {
    fetch('/api/report/sar')
      .then(res => res.json())
      .then(data => setSar(data))
      .catch(err => console.error(err));
  }, []);

  if (!sar) return <div style={{ padding: '24px', color: '#9ca3af' }}>Loading SAR Audit Report...</div>;

  return (
    <div className="glass-card" style={{ margin: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText color="#00f2fe" /> {sar.report_header.report_type}
          </h2>
          <div style={{ fontSize: '0.85rem', color: '#9ca3af' }}>{sar.report_header.regulatory_authority}</div>
        </div>
        <button className="btn-primary" onClick={() => alert('Downloading official FIU-IND SAR PDF report...')}>
          <Download size={16} style={{ marginRight: '6px' }} /> Export SAR PDF
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
        <div style={{ background: 'rgba(255,255,255,0.03)', padding: '16px', borderRadius: '8px' }}>
          <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Total Accounts Audited</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#00f2fe' }}>{sar.summary_statistics.total_accounts_audited}</div>
        </div>
        <div style={{ background: 'rgba(255,255,255,0.03)', padding: '16px', borderRadius: '8px' }}>
          <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Flagged Suspicious</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#ef4444' }}>{sar.summary_statistics.flagged_suspicious_accounts}</div>
        </div>
        <div style={{ background: 'rgba(255,255,255,0.03)', padding: '16px', borderRadius: '8px' }}>
          <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Structuring Events</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f59e0b' }}>{sar.summary_statistics.structuring_events_detected}</div>
        </div>
        <div style={{ background: 'rgba(255,255,255,0.03)', padding: '16px', borderRadius: '8px' }}>
          <div style={{ fontSize: '0.8rem', color: '#9ca3af' }}>Mule Clusters</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#9d4edd' }}>{sar.summary_statistics.mule_clusters_detected}</div>
        </div>
      </div>

      <h3 style={{ fontSize: '1rem', color: '#00f2fe', marginBottom: '12px' }}>Flagged Subjects in Report</h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {sar.flagged_subjects.map((sub, i) => (
          <div key={i} style={{ background: 'rgba(255,255,255,0.02)', padding: '12px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.05)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span className="mono" style={{ fontWeight: 700, color: '#fff' }}>Subject: {sub.subject_id}</span>
              <span className="badge-high">Risk Score: {(sub.mule_probability * 100).toFixed(1)}%</span>
            </div>
            <div style={{ fontSize: '0.85rem', color: '#9ca3af' }}>
              Primary Drivers: {sub.primary_risk_factors.join(' • ')}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
