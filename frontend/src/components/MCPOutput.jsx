import React, { useState } from 'react';

export default function MCPOutput({ mcp, skill, loading, onGenerate }) {
  const [tab, setTab] = useState('mcp');
  const [copied, setCopied] = useState(false);

  const content = tab === 'mcp' ? mcp : skill;

  const handleCopy = () => {
    navigator.clipboard.writeText(content).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div style={{
      background: 'var(--bg2)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius)', padding: '1.25rem'
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14, gap: 12 }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--txt3)', marginBottom: 4 }}>
            MCP server + SKILL.md artifact
          </div>
          <div style={{ fontSize: 12, color: 'var(--txt2)' }}>
            Curated MCP stub built from your top-scoring endpoints
          </div>
        </div>
        {!mcp && !loading && (
          <button onClick={onGenerate} style={{
            fontSize: 12, fontWeight: 500, padding: '7px 16px',
            borderRadius: 'var(--radius-sm)', border: '1px solid var(--border2)',
            background: 'transparent', color: 'var(--accent)', cursor: 'pointer',
            flexShrink: 0, display: 'flex', alignItems: 'center', gap: 6,
            transition: 'background 0.15s'
          }}>
            ✦ Generate
          </button>
        )}
      </div>

      {loading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '1rem 0', color: 'var(--txt2)', fontSize: 13 }}>
          <div style={{
            width: 18, height: 18, border: '2px solid var(--border2)',
            borderTopColor: 'var(--accent)', borderRadius: '50%',
            animation: 'spin 0.8s linear infinite'
          }} />
          Generating artifacts…
        </div>
      )}

      {mcp && !loading && (
        <>
          <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
            {['mcp', 'skill'].map(t => (
              <button key={t} onClick={() => setTab(t)} style={{
                fontSize: 12, padding: '4px 12px',
                borderRadius: 'var(--radius-sm)',
                border: `1px solid ${tab === t ? 'var(--border2)' : 'var(--border)'}`,
                background: tab === t ? 'var(--bg3)' : 'transparent',
                color: tab === t ? 'var(--txt)' : 'var(--txt2)',
                cursor: 'pointer', fontWeight: tab === t ? 500 : 400,
                transition: 'all 0.15s'
              }}>
                {t === 'mcp' ? 'MCP server stub' : 'SKILL.md'}
              </button>
            ))}
          </div>

          <pre style={{
            background: 'var(--bg3)', borderRadius: 'var(--radius-sm)',
            padding: '14px', fontFamily: "'IBM Plex Mono', monospace",
            fontSize: 11, lineHeight: 1.65, color: 'var(--txt2)',
            overflowX: 'auto', overflowY: 'auto',
            maxHeight: 280, border: '1px solid var(--border)',
            whiteSpace: 'pre'
          }}>
            {content}
          </pre>

          <button onClick={handleCopy} style={{
            marginTop: 8, fontSize: 11, padding: '5px 12px',
            borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)',
            background: 'transparent', color: copied ? 'var(--accent)' : 'var(--txt2)',
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5,
            transition: 'color 0.15s'
          }}>
            {copied ? '✓ Copied' : '⧉ Copy'}
          </button>
        </>
      )}
    </div>
  );
}
