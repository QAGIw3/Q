import { w3cwebsocket as W3CWebSocket, IMessageEvent } from "websocket";
import { SearchQuery, SearchResponse } from './types';
import keycloak from "../keycloak";

const API_BASE_URL = process.env.REACT_APP_MANAGERQ_API_URL || 'http://localhost:8000/api/v1';

const getHeaders = () => {
    const headers: { [key: string]: string } = {
        'Content-Type': 'application/json',
    };
    if (keycloak.authenticated && keycloak.token) {
        headers['Authorization'] = `Bearer ${keycloak.token}`;
    }
    return headers;
};

// --- API Calls ---

export const listWorkflows = async (status?: string, skip: number = 0, limit: number = 100) => {
    const params = new URLSearchParams({
        skip: String(skip),
        limit: String(limit),
    });
    if (status) {
        params.append('status', status);
    }
    const response = await fetch(`${API_BASE_URL}/workflows?${params.toString()}`, {
        headers: getHeaders(),
    });
    if (!response.ok) {
        throw new Error('Failed to fetch workflows');
    }
    return response.json();
};

export const getWorkflow = async (workflowId: string) => {
    const response = await fetch(`${API_BASE_URL}/workflows/${workflowId}`, {
        headers: getHeaders(),
    });
    if (!response.ok) {
        throw new Error('Failed to fetch workflow details');
    }
    return response.json();
};

export const createWorkflow = async (prompt: string, context?: object) => {
    const response = await fetch(`${API_BASE_URL}/workflows`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ prompt, context }),
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create workflow');
    }
    return response.json();
};

export const approveWorkflowTask = async (workflowId: string, taskId: string, approved: boolean) => {
    const response = await fetch(`${API_BASE_URL}/workflows/${workflowId}/tasks/${taskId}/approve`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ approved }),
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to approve task');
    }
    // This endpoint returns 204 No Content, so we don't return JSON
};

export const cognitiveSearch = async (searchQuery: SearchQuery): Promise<SearchResponse> => {
    const response = await fetch(`${API_BASE_URL}/search/`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(searchQuery),
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to perform search');
    }
    return response.json();
};

export const respondToApproval = async (workflowId: string, taskId: string, approved: boolean): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/workflows/${workflowId}/tasks/${taskId}/respond`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ approved }),
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to respond to approval');
    }
};

export const knowledgeGraphQuery = async (query: string): Promise<any> => {
    const response = await fetch(`${API_BASE_URL}/search/kg-query`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ query }),
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to perform knowledge graph query');
    }
    return response.json();
};

export const getNodeNeighbors = async (nodeId: string): Promise<any> => {
    const response = await fetch(`${API_BASE_URL}/search/kg-neighbors`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ node_id: nodeId }),
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to fetch node neighbors');
    }
    return response.json();
};

// --- WebSocket Management ---

let socketClient: W3CWebSocket | null = null;

export const connectToDashboardSocket = (onMessageCallback: (message: any) => void) => {
    if (socketClient && socketClient.readyState === socketClient.OPEN) {
        console.log('WebSocket is already connected.');
        return;
    }

    const wsUrl = (API_BASE_URL.replace('http', 'ws')).split('/api/v1')[0] + '/api/v1/dashboard/ws';
    
    socketClient = new W3CWebSocket(wsUrl);

    socketClient.onopen = () => {
        console.log('WebSocket Client Connected');
    };

    socketClient.onmessage = (message: IMessageEvent) => {
        try {
            const data = JSON.parse(message.data as string);
            onMessageCallback(data);
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    };

    socketClient.onerror = (error: Error) => {
        console.error('WebSocket Error:', error);
    };

    socketClient.onclose = () => {
        console.log('WebSocket Client Closed');
        // Optional: Implement automatic reconnection logic here
    };
};

export const disconnectFromDashboardSocket = () => {
    if (socketClient) {
        socketClient.close();
        socketClient = null;
    }
}; 