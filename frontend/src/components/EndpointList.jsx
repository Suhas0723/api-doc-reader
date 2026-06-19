import React, { useState } from 'react';

const METHOD_STYLES = {
  GET:    { bg: 'rgba(74,222,128,0.12)',  color: '#4ade80' },
  POST:   { bg: 'rgba(96,165,250,0.12)',  color: '#60a5fa' },
  PUT:    { bg: 'rgba(245,166,35,0.12)',  color: '#f5a623' },
  DELETE: { bg: 'rgba(255,92,92,0.12)',   color: '#ff5c5c' },
  PATCH:  { bg: 'rgba(167,139,250,0.12)', color: '#a78bfa' },
};

const SMELL_PILL = {
  lazy:       { bg: 'rgba(245,166,35,0.15)',  color: '#f5a623' },
  bloated:    { bg: 'rgba(255,92,92,0.15)',   color: '#ff5c5c' },
  tangled:    { bg: 'rgba(167,139,250,0.15)', color: '#a78bfa' },
  fragmented: { bg: 'rgba(96,165,250,0.15)',  color: '#60a5fa' },
  response:   { bg: 'rgba(255,92,92,0.15)',   color: '#ff5c5c' },
  security:   { bg: 'rgba(245,166,35,0.15)',  color: '#f5a623' },
  input:      { bg: 'rgba(74,222,128,0.15)',  color: '#4ade80' },
};

const scoreColor = (s) => s >= 80 ? '#4ade80' : s >= 60 ? '#f5a623' : s >= 40 ? '#ff8c42' : '#ff5c5c';

function EndpointRow({ ep }) {
  const [open, setOpen] = useState(false);
  const method = (ep.method || 'GET').toUpperCase();
  const mStyle = METHOD_STYLES[method] || METHOD_STYLES.GET;

  return (
    <div
      style={{
        background: 'var(--bg2)',
        border: `1px solid ${open ? 'var(--border2)' : 'var(--border)'}`,
        borderRadius: 'var(--radius)',
        overflow: 'hidden',
        transition: 'border-color 0.15s',
        cursor: 'pointer'
      }}
      onClick={() => setOpen(!open)}
    >
      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{
          fontSize: 10, fontWeight: 600, padding: '3px 8px',
          borderRadius: 4, fontFamily: "'IBM Plex Mono', monospace",
          background: mStyle.bg, color: mStyle.color, flexShrink: 0,
          letterSpacing: '0.04em'
        }}>
          {method}
        </span>
        <span style={{
          fontFamily: "'IBM Plex Mono', monospace", fontSize: 12,
          flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
        }}>
          {ep.path}
        </span>
        <span style={{ fontSize: 13, fontWeight: 600, color: scoreColor(ep.score), flexShrink: 0 }}>
          {ep.score}/100
        </span>
        {(ep.smells || []).map(s => {
          const p = SMELL_PILL[s.toLowerCase()] || { bg: 'rgba(255,255,255,0.08)', color: 'var(--txt2)' };
          return (
            <span key={s} style={{
              fontSize: 10, fontWeight: 500, padding: '2px 8px', borderRadius: 20,
              background: p.bg, color: p.color
            }}>
              {s}
            </span>
          );
        })}
        <span style={{ fontSize: 14, color: 'var(--txt3)', transform: open ? 'rotate(180deg)' : '', transition: 'transform 0.2s', flexShrink: 0 }}>
          ▾
        </span>
      </div>

      {open && (
        <div style={{
          borderTop: '1px solid var(--border)',
          padding: '14px 16px',
          display: 'flex', flexDirection: 'column', gap: 10
        }}>
          <p style={{ fontSize: 13, color: 'var(--txt2)', lineHeight: 1.6 }}>{ep.analysis}</p>
          {(ep.fixes || []).length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {ep.fixes.map((fix, i) => (
                <div key={i} style={{
                  background: 'var(--bg3)', borderRadius: 'var(--radius-sm)',
                  padding: '8px 12px', display: 'flex', gap: 8, alignItems: 'flex-start',
                  fontSize: 12, color: 'var(--txt2)', lineHeight: 1.5
                }}>
                  <span style={{ color: 'var(--accent)', flexShrink: 0, marginTop: 1 }}>→</span>
                  {fix}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function EndpointList({ endpoints }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {endpoints.map((ep, i) => <EndpointRow key={i} ep={ep} />)}
    </div>
  );
}
