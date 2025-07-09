// WebAppQ/app/src/services/authAPI.ts
import { UserCreate } from './types'; // Add UserCreate to types

const AUTHQ_API_URL = process.env.REACT_APP_AUTHQ_API_URL || 'http://localhost:8003/api/v1';

export const login = async (username: string, password: string): Promise<{ access_token: string }> => {
    
    // The TokenRequest in AuthQ expects 'username' and 'password' in the body.
    // It's a POST request.
    const response = await fetch(`${AUTHQ_API_URL}/auth/token`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Login failed');
    }
    
    return response.json();
};

export const register = async (userData: UserCreate): Promise<any> => {
    const response = await fetch(`${AUTHQ_API_URL}/users/register`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(userData),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Registration failed');
    }
    
    return response.json();
}; 