import React, { useState, useEffect } from 'react';
import AgentWorkbench from './components/AgentWorkbench.jsx';
import NetworkGraph from './components/NetworkGraph.jsx';
import AccountsView from './components/AccountsView.jsx';
import SarReportView from './components/SarReportView.jsx';
import './index.css';

const TABS = [
  { id: 'agent',    label: '🤖 Agent Workbench',  description: 'Autonomous NL Query & Execution' },
  { id: 'graph',    label: '🕸️ Entity Graph',       description: 'Unified Cross-Channel Graph' },
  { id: 'accounts', label: '📊 Risk Matrix',        description: 'GNN Account Risk Scores' },
  { id: 'sar',      label: '📋 SAR Report',         description: 'FIU-IND Compliant Audit' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('agent');
  const [systemStatus, setSystemStatus] = useState(null);

  useEffect(() => {
    fetch('/api/status')
      .then(r => r.json())
      .then(d => setSystemStatus(d))
      .catch(() => {});
  }, []);

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* Header */}
      <header style={{
        borderBottom: '1px solid rgba(0,242,254,0.12)',
        padding: '0 32px',
        background: 'rgba(10,13,20,0.95)',
        backdropFilter: 'blur(16px)',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: '64px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {/* Logo */}
          <div style={{
            width: '38px', height: '38px',
            background: 'linear-gradient(135deg, #00f2fe 0%, #9d4edd 100%)',
            borderRadius: '8px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 800, fontSize: '1.1rem'
          }}>M</div>
          <div>
            <div style={{ fontWeight: 800, fontSize: '1.1rem', letterSpacing: '0.03em' }}>
              Mule<span style={{ color: '#00f2fe' }}>Trace</span>
            </div>
            <div style={{ fontSize: '0.7rem', color: '#9ca3af', fontWeight: 500, letterSpacing: '0.08em' }}>
              AUTONOMOUS AGENTIC AML INTELLIGENCE
            </div>
          </div>
        </div>

        {/* Status Pill */}
        {systemStatus && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px', fontSize: '0.8rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{
                width: '8px', height: '8px', borderRadius: '50%',
                background: systemStatus.model_trained ? '#10b981' : '#f59e0b',
                display: 'inline-block', boxShadow: '0 0 8px #10b981'
              }} />
              <span style={{ color: '#9ca3af' }}>
                {systemStatus.model_trained ? 'Agent Online' : 'Initializing...'}
              </span>
            </div>
            <div style={{ color: '#9ca3af' }}>
              <span style={{ color: '#00f2fe', fontWeight: 700 }}>{systemStatus.total_accounts}</span> accounts scanned
            </div>
          </div>
        )}
      </header>

      {/* Tab Navigation */}
      <nav style={{
        display: 'flex',
        gap: '4px',
        padding: '16px 32px 0',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        background: 'rgba(10,13,20,0.6)',
      }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            id={`tab-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '10px 20px',
              borderRadius: '8px 8px 0 0',
              border: 'none',
              background: activeTab === tab.id
                ? 'rgba(0,242,254,0.08)'
                : 'transparent',
              color: activeTab === tab.id ? '#00f2fe' : '#9ca3af',
              fontWeight: activeTab === tab.id ? 700 : 400,
              fontSize: '0.9rem',
              cursor: 'pointer',
              borderBottom: activeTab === tab.id ? '2px solid #00f2fe' : '2px solid transparent',
              transition: 'all 0.2s ease',
              fontFamily: 'Inter, sans-serif',
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Tab Content */}
      <main style={{ padding: '8px 8px 40px' }}>
        {activeTab === 'agent'    && <AgentWorkbench />}
        {activeTab === 'graph'    && <NetworkGraph />}
        {activeTab === 'accounts' && <AccountsView />}
        {activeTab === 'sar'      && <SarReportView />}
      </main>

      {/* Footer */}
      <footer style={{
        textAlign: 'center',
        padding: '16px',
        color: '#4b5563',
        fontSize: '0.75rem',
        borderTop: '1px solid rgba(255,255,255,0.04)'
      }}>
        MuleTrace — Autonomous Agentic AML &amp; Cross-Channel Fraud Intelligence System
      </footer>
    </div>
  );
}
