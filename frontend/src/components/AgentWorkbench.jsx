import React, { useState } from 'react';
import { Bot, Send, ShieldAlert, Cpu, CheckCircle2, ArrowRight } from 'lucide-react';

export default function AgentWorkbench() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [agentResponse, setAgentResponse] = useState(null);

  const presetQueries = [
    "Find structuring patterns in the last 30 days",
    "Which customers made 10+ transactions under $10,000?",
    "Is customer ID ACC-00001 suspicious?",
    "Perform automated EDA on high-volume transactions",
  ];

  const handleQuery = async (queryText) => {
    const textToRun = queryText || query;
    if (!textToRun.trim()) return;

    setLoading(true);
    try {
      const res = await fetch('/api/agent/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: textToRun })
      });
      const data = await res.json();
      setAgentResponse(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', padding: '24px' }}>
      {/* Left Column: Analyst Chat & Preset Chips */}
      <div className="glass-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '20px' }}>
          <Bot size={28} color="#00f2fe" />
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Autonomous Analyst Workbench</h2>
            <p style={{ fontSize: '0.85rem', color: '#9ca3af' }}>Query-Driven Agentic AML & Pattern Detection Engine</p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
          <input
            type="text"
            placeholder="Ask agent (e.g., 'Find structuring patterns under $10k')..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
            style={{
              flex: 1,
              padding: '12px 16px',
              borderRadius: '8px',
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(0,0,0,0.4)',
              color: '#fff',
              outline: 'none'
            }}
          />
          <button className="btn-primary" onClick={() => handleQuery()} disabled={loading}>
            {loading ? 'Thinking...' : <Send size={18} />}
          </button>
        </div>

        <div style={{ marginBottom: '24px' }}>
          <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#9ca3af', fontWeight: 600 }}>Preset Benchmark Queries for Judges:</span>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '8px' }}>
            {presetQueries.map((q, idx) => (
              <button
                key={idx}
                onClick={() => { setQuery(q); handleQuery(q); }}
                style={{
                  background: 'rgba(0, 242, 254, 0.08)',
                  border: '1px solid rgba(0, 242, 254, 0.2)',
                  color: '#00f2fe',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  fontSize: '0.8rem',
                  cursor: 'pointer'
                }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Dynamic Execution Plan Visualizer */}
        {agentResponse && (
          <div style={{ marginTop: '20px', paddingTop: '20px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
            <h3 style={{ fontSize: '1rem', color: '#00f2fe', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Cpu size={18} /> Dynamic Agent Execution Trace ({agentResponse.execution_time_ms} ms)
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {agentResponse.execution_plan.map((step, idx) => (
                <div key={idx} style={{ background: 'rgba(255,255,255,0.03)', padding: '10px 14px', borderRadius: '6px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <CheckCircle2 size={16} color="#10b981" />
                  <span className="mono" style={{ fontSize: '0.8rem', color: '#00f2fe', fontWeight: 600 }}>[{step.tool}]</span>
                  <span style={{ fontSize: '0.85rem', color: '#d1d5db' }}>{step.reason}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Right Column: Execution Output & Escalation Panel */}
      <div className="glass-card">
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldAlert size={24} color="#ef4444" /> Agentic Audit Results & Escalation
        </h2>

        {agentResponse ? (
          <div>
            <div style={{ background: 'rgba(0,242,254,0.05)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(0,242,254,0.2)', marginBottom: '16px' }}>
              <div style={{ fontSize: '0.85rem', color: '#9ca3af', marginBottom: '4px' }}>Detected Intent</div>
              <div className="mono" style={{ color: '#00f2fe', fontWeight: 700 }}>{agentResponse.intent}</div>
              <div style={{ fontSize: '0.9rem', marginTop: '8px', color: '#f3f4f6' }}>
                {agentResponse.tool_results.summary}
              </div>
            </div>

            {/* Display Structuring / Aggregation Results */}
            {agentResponse.tool_results.structuring_transactions && (
              <div>
                <h4 style={{ fontSize: '0.9rem', color: '#fbbf24', marginBottom: '8px' }}>Flagged Sub-Threshold Structuring Transfers</h4>
                <div style={{ maxHeight: '250px', overflowY: 'auto' }}>
                  {agentResponse.tool_results.structuring_transactions.map((st, i) => (
                    <div key={i} style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '6px', marginBottom: '8px', fontSize: '0.85rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span className="mono" style={{ color: '#00f2fe' }}>{st.source_account} → {st.target_account}</span>
                        <span style={{ color: '#ef4444', fontWeight: 700 }}>${st.amount.toLocaleString()}</span>
                      </div>
                      <div style={{ color: '#9ca3af', fontSize: '0.75rem', marginTop: '4px' }}>{st.explanation}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Display Single Entity Lookup */}
            {agentResponse.tool_results.single_entity && (
              <div style={{ background: 'rgba(239, 68, 68, 0.08)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 700 }}>Customer ID: {agentResponse.tool_results.single_entity.account_id}</span>
                  <span className={`badge-${agentResponse.tool_results.single_entity.risk_tier.toLowerCase()}`}>
                    {agentResponse.tool_results.single_entity.risk_tier} RISK
                  </span>
                </div>
                <div style={{ marginTop: '8px', fontSize: '0.85rem', color: '#d1d5db' }}>
                  {agentResponse.tool_results.single_entity.explanation}
                </div>
                <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
                  <button className="btn-primary" style={{ background: '#ef4444', fontSize: '0.8rem' }}>File SAR Report</button>
                  <button className="btn-primary" style={{ background: '#f59e0b', fontSize: '0.8rem' }}>Flag for Review</button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ color: '#9ca3af', textAlign: 'center', padding: '60px 0', fontSize: '0.9rem' }}>
            Enter a query or select a preset benchmark chip above to view live agent orchestration and XAI explanations.
          </div>
        )}
      </div>
    </div>
  );
}
