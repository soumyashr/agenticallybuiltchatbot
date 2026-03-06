import { THEME } from '../../config/theme';

const STATUS_COLORS = {
  UPLOADED:  THEME.info,
  INGESTING: THEME.warning,
  INGESTED:  THEME.green,
  FAILED:    THEME.error,
};

export default function DocumentList({ docs, onIngest, onDelete, loading }) {
  const all = [...(docs.pending || []), ...(docs.ingested || []), ...(docs.failed || [])];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <h3 style={{ color: THEME.textLight, fontSize: 15, fontWeight: 600 }}>
          Documents ({docs.total || 0})
        </h3>
        {(docs.pending || []).length > 0 && (
          <button onClick={onIngest} disabled={loading}
            style={{
              padding: '7px 16px', background: THEME.green, color: THEME.buttonText,
              border: 'none', borderRadius: 6, fontSize: 12, fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer', fontFamily: THEME.fontBase,
            }}>
            {loading ? 'Ingesting…' : `Ingest Now (${(docs.pending || []).length})`}
          </button>
        )}
      </div>
      {all.length === 0 ? (
        <p style={{ color: THEME.textMuted, fontSize: 13, textAlign: 'center', padding: '30px 0' }}>
          No documents yet. Upload a PDF to get started.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {all.map(doc => (
            <div key={doc.id} style={{
              padding: '12px 14px', background: THEME.bgCard,
              borderRadius: 8, border: `1px solid ${THEME.bgBorder}`,
              display: 'flex', alignItems: 'center', gap: 12,
            }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 13, fontWeight: 600, color: THEME.textLight, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  📄 {doc.display_name}
                </p>
                <p style={{ fontSize: 11, color: THEME.textMuted }}>
                  Roles: {doc.allowed_roles?.join(', ')}
                  {doc.chunk_count > 0 && ` · ${doc.chunk_count} chunks`}
                </p>
              </div>
              <span style={{
                fontSize: 10, fontWeight: 600, padding: '3px 9px', borderRadius: 10,
                background: 'transparent', border: `1px solid ${STATUS_COLORS[doc.status] || THEME.bgBorder}`,
                color: STATUS_COLORS[doc.status] || THEME.textMuted,
                whiteSpace: 'nowrap',
              }}>{doc.status}</span>
              <button onClick={() => onDelete(doc.id)} disabled={loading}
                style={{
                  background: 'transparent', border: 'none', color: THEME.textMuted,
                  cursor: loading ? 'not-allowed' : 'pointer', fontSize: 15, padding: '2px 6px',
                }}>✕</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
