// WebAppQ/app/src/services/h2mAPI.ts
import { FeedbackEvent, UserCreate } from './types';
import keycloak from '../keycloak';

const API_BASE_URL = process.env.REACT_APP_H2M_API_URL || 'http://localhost:8002/api/v1';

// This is a simplified example. In a real app, you would have a more robust
// way of handling headers and authentication, likely shared with managerAPI.ts.
const getHeaders = () => {
    const headers: { [key: string]: string } = {
        'Content-Type': 'application/json',
    };
    if (keycloak.authenticated && keycloak.token) {
        headers['Authorization'] = `Bearer ${keycloak.token}`;
    }
    return headers;
};

export const submitFeedback = async (feedback: FeedbackEvent): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/feedback`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(feedback),
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to submit feedback');
    }
    // The endpoint returns 202 Accepted, so no body to parse.
}; 