import React from 'react';

const scoreColor = (score) => {
  if (score >= 80) return '#4ade80';
  if (score >= 60) return '#f5a623';
  if (score >= 40) return '#ff8c42';
  return '#ff5c5c';
};

const gradeLabel = (score) => {
  if (score >= 80) return { label: 'Agent-ready', color: '#4ade80', bg: 'rgba(74,222,128,0.12)' };
  if (score >= 60) return { label: 'Needs work', color: '#f5a623', bg: 'rgba(245,166,35,0.12)' };
  if (score >= 40) return { label: 'High risk', color: '#ff8c42', bg: 'rgba(255,140,66,0.12)' };
  return { label: 'Not agent-usable', color: '#ff5c5c', bg: 'rgba(255,92,92,0.12)' };
};

export default function ScoreRing({ score, size = 110 }) {
  const r = (size / 2) - 8;
  const circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  const color = scoreColor(score);
  const grade = gradeLabel(score);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
      <div style={{ position: 'relative', width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="7"
          />
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none" stroke={color} strokeWidth="7"
            strokeDasharray={`${dash.toFixed(1)} ${circ.toFixed(1)}`}
            strokeLinecap="round"
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{ transition: 'stroke-dasharray 0.9s ease' }}
          />
        </svg>
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center'
        }}>
          <span style={{ fontSize: 30, fontWeight: 700, lineHeight: 1, color }}>{score}</span>
          <span style={{ fontSize: 11, color: 'var(--txt3)', marginTop: 2 }}>/100</span>
        </div>
      </div>
      <span style={{
        fontSize: 11, fontWeight: 500, padding: '3px 10px',
        borderRadius: 20, background: grade.bg, color: grade.color,
        letterSpacing: '0.04em'
      }}>
        {grade.label}
      </span>
    </div>
  );
}
