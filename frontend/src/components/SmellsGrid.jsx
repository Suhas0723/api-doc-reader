import React from 'react';

const SMELL_META = {
  lazy:       { label: 'Lazy',       color: '#f5a623', desc: 'Vague summaries, undocumented params' },
  bloated:    { label: 'Bloated',    color: '#ff5c5c', desc: 'Verbose descriptions, low info density' },
  tangled:    { label: 'Tangled',    color: '#a78bfa', desc: 'Mixes unrelated concerns' },
  fragmented: { label: 'Fragmented', color: '#60a5fa', desc: 'Key info scattered, no linkage' },
  response:   { label: 'Response',   color: '#ff5c5c', desc: 'Missing status codes or error schemas' },
  security:   { label: 'Security',   color: '#f5a623', desc: 'Missing auth schemes or scopes' },
  input:      { label: 'Input',      color: '#4ade80', desc: 'Undescribed request body fields' },
};

export default function SmellsGrid({ smells }) {
  const maxVal = Math.max(...Object.values(smells), 1);

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
      gap: 10
    }}>
      {Object.entries(smells).map(([key, count]) => {
        const meta = SMELL_META[key] || { label: key, color: '#888', desc: '' };
        const pct = Math.round((count / maxVal) * 100);
        return (
          <div key={key} style={{
            background: 'var(--bg3)',
            borderRadius: 'var(--radius-sm)',
            padding: '12px 14px',
            display: 'flex', flexDirection: 'column', gap: 6
          }}>
            <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: meta.color }}>
              {meta.label}
            </span>
            <span style={{ fontSize: 26, fontWeight: 700, lineHeight: 1 }}>{count}</span>
            <div style={{ height: 3, background: 'var(--bg4)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ height: 3, width: `${pct}%`, background: meta.color, borderRadius: 2, transition: 'width 0.6s ease' }} />
            </div>
            <span style={{ fontSize: 11, color: 'var(--txt2)', lineHeight: 1.4 }}>{meta.desc}</span>
          </div>
        );
      })}
    </div>
  );
}
