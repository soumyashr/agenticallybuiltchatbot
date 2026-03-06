import { useState } from 'react';
import { useAuthContext } from '../context/AuthContext';

export function useAuth() {
  const { auth, login, logout } = useAuthContext();
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');

  async function handleLogin(username, password) {
    setLoading(true);
    setError('');
    try {
      await login(username, password);
    } catch (err) {
      setError(err.message || 'Login failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  }

  return {
    auth,
    loading,
    error,
    handleLogin,
    logout,
    isAdmin:   auth?.role === 'admin',
    isFaculty: auth?.role === 'faculty',
    isStudent: auth?.role === 'student',
    initial:   auth?.username?.[0]?.toUpperCase() ?? 'U',
  };
}
