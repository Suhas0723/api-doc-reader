import React, { useState, useRef } from 'react';
import ScoreRing from './components/ScoreRing';
import SmellsGrid from './components/SmellsGrid';
import EndpointList from './components/EndpointList';
import MCPOutput from './components/MCPOutput';
import { SAMPLES } from './samples';

const Section = ({ title, children }) => (
  <div>
    <div style={{
      fontSize: 10, fontWeight: 600, letterSpacing: '0.08em',
      textTransform: 'uppercase', color: 'var(--txt3)', marginBottom: 12
    }}>
      {title}
    </div>
    {children}
  </div>
);

const Divider = () => (
  <div style={{ height: 1, background: 'var(--border)' }} />
);

const TAB_STYLE_BASE = {
  fontSize: 12, fontWeight: 500, padding: '6px 14px',
  borderRadius: 'var(--radius-sm)', border: '1px solid transparent',
  cursor: 'pointer', transition: 'all 0.15s', background: 'transparent'
};

const TABS = [
  { id: 'spec', label: 'Paste spec' },
  { id: 'url', label: 'URL / web docs' },
  { id: 'file', label: 'Upload file' },
];

function ProseSourceBanner({ source }) {
  if (!source) return null;
  const items = [
    source.api_name && { label: 'API', val: source.api_name },
    source.base_url && { label: 'Base URL', val: source.base_url },
    source.auth_mechanism && { label: 'Auth', val: source.auth_mechanism },
  ].filter(Boolean);

  return (
    <div style={{
      background: 'rgba(200,240,96,0.06)', border: '1px solid rgba(200,240,96,0.2)',
      borderRadius: 'var(--radius)', padding: '12px 16px',
      display: 'flex', flexDirection: 'column', gap: 8
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--accent)' }}>
        Scored from prose docs — no formal OpenAPI spec
      </div>
      {items.length > 0 && (
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {items.map(({ label, val }) => (
            <div key={label} style={{ fontSize: 12, color: 'var(--txt2)' }}>
              <span style={{ color: 'var(--txt3)' }}>{label}: </span>{val}
            </div>
          ))}
        </div>
      )}
      {source.missing_info?.length > 0 && (
        <div style={{ fontSize: 12, color: 'var(--txt3)', lineHeight: 1.5 }}>
          <span style={{ color: 'var(--txt2)', fontWeight: 500 }}>Gaps detected: </span>
          {source.missing_info.slice(0, 3).join(' · ')}
          {source.missing_info.length > 3 && ` +${source.missing_info.length - 3} more`}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState('spec');
  const [spec, setSpec] = useState('');
  const [url, setUrl] = useState('');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mcpLoading, setMcpLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [mcpData, setMcpData] = useState(null);
  const [error, setError] = useState('');
  const [proseText, setProseText] = useState(''); // extracted text for MCP generation
  const fileRef = useRef();

  const reset = () => { setResults(null); setMcpData(null); setError(''); setProseText(''); };

  const handleAnalyze = async () => {
    reset();
    setLoading(true);

    try {
      if (tab === 'spec') {
        if (!spec.trim()) { setError('Please paste an OpenAPI spec first.'); return; }
        const res = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ spec })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Analysis failed');
        setResults(data);

      } else {
        // For URL and file, first ingest then analyze-prose
        let text = '';

        if (tab === 'url') {
          if (!url.trim()) { setError('Please enter a URL.'); return; }
          const ingestRes = await fetch('/api/ingest/url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
          });
          const ingestData = await ingestRes.json();
          if (!ingestRes.ok) throw new Error(ingestData.error || 'Failed to fetch URL');
          text = ingestData.text;

        } else {
          if (!file) { setError('Please select a file.'); return; }
          const formData = new FormData();
          formData.append('file', file);
          const ingestRes = await fetch('/api/ingest/file', { method: 'POST', body: formData });
          const ingestData = await ingestRes.json();
          if (!ingestRes.ok) throw new Error(ingestData.error || 'Failed to read file');
          text = ingestData.text;
        }

        setProseText(text);
        const scoreRes = await fetch('/api/analyze-prose', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        const scoreData = await scoreRes.json();
        if (!scoreRes.ok) throw new Error(scoreData.error || 'Analysis failed');
        setResults(scoreData);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateMCP = async () => {
    if (!results) return;
    setMcpLoading(true);

    try {
      const res = await fetch('/api/generate-mcp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ spec: tab === 'spec' ? spec : proseText, analysis: results })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Generation failed');
      setMcpData(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setMcpLoading(false);
    }
  };

  const canAnalyze = tab === 'spec' ? !!spec.trim() : tab === 'url' ? !!url.trim() : !!file;

  return (
    <div style={{ minHeight: '100vh', padding: '0 0 4rem' }}>
      {/* Top bar */}
      <div style={{
        borderBottom: '1px solid var(--border)',
        padding: '1rem 2rem',
        display: 'flex', alignItems: 'center', gap: 12
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: 6,
          background: 'var(--accent)', display: 'flex', alignItems: 'center',
          justifyContent: 'center', fontSize: 14
        }}>◎</div>
        <span style={{ fontWeight: 700, fontSize: 15, letterSpacing: '-0.01em' }}>
          API Agent-Readiness Scorer
        </span>
        <span style={{
          fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 20,
          background: 'rgba(200,240,96,0.12)', color: 'var(--accent)',
          letterSpacing: '0.06em', textTransform: 'uppercase', marginLeft: 4
        }}>
          MVP
        </span>
      </div>

      <div style={{ maxWidth: 860, margin: '0 auto', padding: '2rem 1.5rem', display: 'flex', flexDirection: 'column', gap: '2rem' }}>

        {/* Hero text */}
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.2, marginBottom: 8 }}>
            Is your API ready for AI agents?
          </h1>
          <p style={{ fontSize: 14, color: 'var(--txt2)', lineHeight: 1.6, maxWidth: 580 }}>
            Score any API documentation against the Hermes rubric — paste a spec, drop in a URL, or upload a PDF.
            Works even when there's no OpenAPI spec.
          </p>
        </div>

        {/* Input panel */}
        <div style={{
          background: 'var(--bg2)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', padding: '1.25rem',
          display: 'flex', flexDirection: 'column', gap: 12
        }}>
          {/* Tabs */}
          <div style={{ display: 'flex', gap: 4 }}>
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => { setTab(t.id); reset(); }}
                style={{
                  ...TAB_STYLE_BASE,
                  color: tab === t.id ? 'var(--txt)' : 'var(--txt3)',
                  borderColor: tab === t.id ? 'var(--border2)' : 'transparent',
                  background: tab === t.id ? 'var(--bg3)' : 'transparent'
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          {tab === 'spec' && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6 }}>
                <span style={{ fontSize: 12, color: 'var(--txt3)' }}>Examples:</span>
                {Object.entries({ minimal: 'Minimal', good: 'Well-documented', smelly: 'Smell-heavy' }).map(([k, label]) => (
                  <button
                    key={k}
                    onClick={() => { setSpec(SAMPLES[k]); setError(''); }}
                    style={{
                      fontSize: 11, padding: '3px 10px',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border2)',
                      background: 'transparent', color: 'var(--txt2)',
                      cursor: 'pointer'
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <textarea
                value={spec}
                onChange={e => setSpec(e.target.value)}
                placeholder={`openapi: "3.0.0"\ninfo:\n  title: My API\n  ...\npaths:\n  /users:\n    get:\n      ...`}
                style={{
                  width: '100%', minHeight: 200,
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: 12,
                  background: 'var(--bg3)', color: 'var(--txt)',
                  border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
                  padding: '12px 14px', resize: 'vertical', lineHeight: 1.6, outline: 'none'
                }}
                onFocus={e => e.target.style.borderColor = 'var(--border2)'}
                onBlur={e => e.target.style.borderColor = 'var(--border)'}
              />
            </>
          )}

          {tab === 'url' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 12, color: 'var(--txt3)', lineHeight: 1.5 }}>
                Paste a link to any API docs page — Confluence, Notion, a portal, a GitHub README, or any public URL.
              </div>
              <input
                type="url"
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://docs.example.com/api"
                style={{
                  fontFamily: "'IBM Plex Mono', monospace", fontSize: 13,
                  background: 'var(--bg3)', color: 'var(--txt)',
                  border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
                  padding: '10px 14px', outline: 'none', width: '100%'
                }}
                onFocus={e => e.target.style.borderColor = 'var(--border2)'}
                onBlur={e => e.target.style.borderColor = 'var(--border)'}
                onKeyDown={e => e.key === 'Enter' && canAnalyze && handleAnalyze()}
              />
            </div>
          )}

          {tab === 'file' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 12, color: 'var(--txt3)', lineHeight: 1.5 }}>
                Upload a PDF, Markdown, or plain text file containing API documentation.
              </div>
              <div
                onClick={() => fileRef.current?.click()}
                onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) setFile(f); }}
                style={{
                  border: '2px dashed var(--border2)', borderRadius: 'var(--radius-sm)',
                  padding: '2rem 1rem', textAlign: 'center', cursor: 'pointer',
                  background: file ? 'rgba(200,240,96,0.04)' : 'var(--bg3)',
                  transition: 'all 0.15s'
                }}
              >
                {file ? (
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--txt)' }}>{file.name}</div>
                    <div style={{ fontSize: 12, color: 'var(--txt3)', marginTop: 4 }}>
                      {(file.size / 1024).toFixed(0)} KB · click to change
                    </div>
                  </div>
                ) : (
                  <div>
                    <div style={{ fontSize: 14, color: 'var(--txt2)' }}>Drop a file here or click to browse</div>
                    <div style={{ fontSize: 12, color: 'var(--txt3)', marginTop: 4 }}>PDF, .txt, .md, .html — up to 5 MB</div>
                  </div>
                )}
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.txt,.md,.rst,.html,.htm"
                onChange={e => { if (e.target.files[0]) setFile(e.target.files[0]); }}
                style={{ display: 'none' }}
              />
            </div>
          )}

          {error && (
            <div style={{
              background: 'rgba(255,92,92,0.1)', border: '1px solid rgba(255,92,92,0.3)',
              borderRadius: 'var(--radius-sm)', padding: '10px 14px',
              fontSize: 13, color: '#ff5c5c'
            }}>
              {error}
            </div>
          )}

          {/* Loading note for prose tabs */}
          {loading && tab !== 'spec' && (
            <div style={{ fontSize: 12, color: 'var(--txt3)' }}>
              Fetching docs → extracting API structure → scoring… this takes ~15 seconds.
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              onClick={handleAnalyze}
              disabled={loading}
              style={{
                fontSize: 13, fontWeight: 600, padding: '9px 22px',
                borderRadius: 'var(--radius-sm)',
                border: 'none', background: loading ? 'var(--bg4)' : 'var(--accent)',
                color: loading ? 'var(--txt3)' : '#0e0e10',
                cursor: loading ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', gap: 8,
                transition: 'all 0.15s'
              }}
            >
              {loading ? (
                <>
                  <div style={{
                    width: 14, height: 14, border: '2px solid var(--txt3)',
                    borderTopColor: 'var(--txt2)', borderRadius: '50%',
                    animation: 'spin 0.8s linear infinite'
                  }} />
                  {tab === 'spec' ? 'Analyzing…' : 'Fetching & analyzing…'}
                </>
              ) : (
                <>◎ {tab === 'spec' ? 'Analyze spec' : tab === 'url' ? 'Analyze URL' : 'Analyze file'}</>
              )}
            </button>
          </div>
        </div>

        {/* Results */}
        {results && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>

            {/* Prose source banner */}
            {results._source && <ProseSourceBanner source={results._source} />}

            {/* Score hero */}
            <div style={{
              background: 'var(--bg2)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius)', padding: '1.5rem',
              display: 'flex', gap: '1.5rem', alignItems: 'center', flexWrap: 'wrap'
            }}>
              <ScoreRing score={results.overallScore} />
              <div style={{ flex: 1, minWidth: 200, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ fontSize: 16, fontWeight: 600 }}>Agent-readiness score</div>
                <div style={{ fontSize: 13, color: 'var(--txt2)', lineHeight: 1.6 }}>{results.summary}</div>
              </div>
              <div style={{ display: 'flex', gap: 10 }}>
                {[
                  { label: 'Total smells', val: results.totalSmells, color: '#ff5c5c' },
                  { label: 'Endpoints', val: (results.endpoints || []).length, color: 'var(--txt)' }
                ].map(stat => (
                  <div key={stat.label} style={{
                    background: 'var(--bg3)', borderRadius: 'var(--radius-sm)',
                    padding: '10px 16px', display: 'flex', flexDirection: 'column', gap: 4, minWidth: 90
                  }}>
                    <span style={{ fontSize: 11, color: 'var(--txt2)' }}>{stat.label}</span>
                    <span style={{ fontSize: 24, fontWeight: 700, color: stat.color }}>{stat.val}</span>
                  </div>
                ))}
              </div>
            </div>

            <Divider />

            <Section title="Documentation smell breakdown">
              <SmellsGrid smells={results.smells || {}} />
            </Section>

            <Divider />

            <Section title="Endpoint analysis — click to expand">
              <EndpointList endpoints={results.endpoints || []} />
            </Section>

            <Divider />

            <Section title="Top recommendations — prioritized by impact">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {(results.recommendations || []).map((rec, i) => (
                  <div key={i} style={{
                    background: 'var(--bg2)', border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)', padding: '12px 16px',
                    display: 'flex', gap: 14, alignItems: 'flex-start'
                  }}>
                    <div style={{
                      width: 24, height: 24, borderRadius: '50%',
                      background: 'var(--bg3)', display: 'flex',
                      alignItems: 'center', justifyContent: 'center',
                      fontSize: 11, fontWeight: 600, color: 'var(--accent)',
                      flexShrink: 0
                    }}>
                      {i + 1}
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 3 }}>{rec.title}</div>
                      <div style={{ fontSize: 12, color: 'var(--txt2)', lineHeight: 1.5 }}>{rec.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
            </Section>

            <Divider />

            <MCPOutput
              mcp={mcpData?.mcp || ''}
              skill={mcpData?.skill || ''}
              loading={mcpLoading}
              onGenerate={handleGenerateMCP}
            />
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        textarea::placeholder { color: var(--txt3); }
        input::placeholder { color: var(--txt3); }
      `}</style>
    </div>
  );
}
