import React, { useEffect, useState } from 'react';

export default function AccountsView() {
  const [accounts, setAccounts] = useState([]);

  useEffect(() => {
    fetch('/api/accounts')
      .then(res => res.json())
      .then(data => setAccounts(data.accounts || []))
      .catch(err => console.error(err));
  }, []);

  return (
    <div className="glass-card" style={{ margin: '24px' }}>
      <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '16px' }}>
        Accounts Risk Matrix & Neural Inference Scores
      </h2>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#9ca3af' }}>
              <th style={{ padding: '12px' }}>Account ID</th>
              <th style={{ padding: '12px' }}>GNN Mule Prob</th>
              <th style={{ padding: '12px' }}>Risk Level</th>
              <th style={{ padding: '12px' }}>Recommended Action</th>
              <th style={{ padding: '12px' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((acc, i) => (
              <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                <td className="mono" style={{ padding: '12px', color: '#00f2fe' }}>{acc.account_id}</td>
                <td className="mono" style={{ padding: '12px' }}>{(acc.mule_probability * 100).toFixed(1)}%</td>
                <td style={{ padding: '12px' }}>
                  <span className={`badge-${acc.risk_level.toLowerCase()}`}>{acc.risk_level}</span>
                </td>
                <td style={{ padding: '12px', fontWeight: 600 }}>{acc.recommended_action}</td>
                <td style={{ padding: '12px', color: acc.is_flagged ? '#ef4444' : '#10b981' }}>
                  {acc.is_flagged ? 'FLAGGED' : 'CLEAR'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
