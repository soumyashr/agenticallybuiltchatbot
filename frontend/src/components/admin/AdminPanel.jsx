import { useEffect } from 'react';
import { THEME } from '../../config/theme';
import { useDocuments } from '../../hooks/useDocuments';
import DocumentUpload from './DocumentUpload';
import DocumentList from './DocumentList';

export default function AdminPanel({ token }) {
  const { docs, loading, error, success, refresh, upload, ingest, remove } = useDocuments(token);

  useEffect(() => { refresh(); }, []);

  return (
    <div style={{
      flex: 1, overflowY: 'auto', padding: '24px',
      background: THEME.bgDeep,
    }}>
      <h2 style={{ color: THEME.textLight, fontSize: 20, fontWeight: 700, marginBottom: 20 }}>
        Document Management
      </h2>

      {error && (
        <div style={{ padding: '10px 14px', background: THEME.errorBg, border: `1px solid ${THEME.error}`, borderRadius: 8, color: THEME.error, fontSize: 13, marginBottom: 16 }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{ padding: '10px 14px', background: THEME.greenDim, border: `1px solid ${THEME.green}`, borderRadius: 8, color: THEME.green, fontSize: 13, marginBottom: 16 }}>
          {success}
        </div>
      )}

      <DocumentUpload onUpload={upload} loading={loading} />
      <DocumentList docs={docs} onIngest={ingest} onDelete={remove} loading={loading} />
    </div>
  );
}
