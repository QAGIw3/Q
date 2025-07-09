import React, { createContext, useState, useEffect, ReactNode } from 'react';
import keycloak from './keycloak';

interface AuthContextType {
  isAuthenticated: boolean;
  token: string | undefined;
  claims: any; // You can define a more specific type for claims
  login: () => void;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState<string | undefined>(undefined);
  const [claims, setClaims] = useState<any>(null);

  useEffect(() => {
    const initAuth = async () => {
      try {
        const authenticated = await keycloak.init({
          onLoad: 'login-required',
          silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html'
        });
        
        setIsAuthenticated(authenticated);
        if (authenticated) {
          setToken(keycloak.token);
          setClaims(keycloak.tokenParsed);
        }
      } catch (error) {
        console.error("Failed to initialize adapter:", error);
      }
    };
    initAuth();
  }, []);

  const login = () => {
    keycloak.login();
  };

  const logout = () => {
    keycloak.logout();
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, token, claims, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}; 