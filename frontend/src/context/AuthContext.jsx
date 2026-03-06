import { createContext, useContext, useState, useCallback } from 'react';
import { login as apiLogin } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => {
    const stored = sessionStorage.getItem('hm_auth');
    return stored ? JSON.parse(stored) : null;
  });

  const login = useCallback(async (username, password) => {
    const data = await apiLogin(username, password);
    const authData = {
      token:    data.access_token,
      username: data.username,
      role:     data.role,
    };
    sessionStorage.setItem('hm_auth', JSON.stringify(authData));
    setAuth(authData);
    return authData;
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem('hm_auth');
    setAuth(null);
  }, []);

  return (
    <AuthContext.Provider value={{ auth, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuthContext must be used inside AuthProvider');
  return ctx;
}
