import { useState, useCallback } from 'react';
import {
  fetchDocuments, uploadDocument,
  ingestDocuments, deleteDocument,
} from '../services/api';

export function useDocuments(token) {
  const [docs,    setDocs]    = useState({ pending: [], ingested: [], failed: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');
  const [success, setSuccess] = useState('');

  const refresh = useCallback(async () => {
    try {
      const data = await fetchDocuments(token);
      setDocs(data);
    } catch { /* ignore poll errors */ }
  }, [token]);

  const upload = useCallback(async (file, displayName, allowedRoles) => {
    setLoading(true); setError(''); setSuccess('');
    try {
      await uploadDocument(token, file, displayName, allowedRoles);
      setSuccess(`"${displayName}" uploaded. Click Ingest Now to make it searchable.`);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, refresh]);

  const ingest = useCallback(async () => {
    setLoading(true); setError(''); setSuccess('');
    try {
      const result = await ingestDocuments(token);
      setSuccess(result.message);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, refresh]);

  const remove = useCallback(async (docId) => {
    setLoading(true); setError(''); setSuccess('');
    try {
      const result = await deleteDocument(token, docId);
      setSuccess(`"${result.filename}" deleted.`);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, refresh]);

  return { docs, loading, error, success, refresh, upload, ingest, remove };
}
