// WebAppQ/app/src/services/workflowBuilderAPI.ts
import keycloak from '../keycloak';
import { Workflow } from './types'; // Assuming a Workflow type exists

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

export const saveWorkflow = async (workflowData: any): Promise<Workflow> => {
    // Logic to transform react-flow state into the Workflow model format
    const workflowPayload = {
        original_prompt: "User-created workflow",
        tasks: [], // Transform nodes and edges to tasks
        shared_context: {},
    };

    const response = await fetch(`${API_BASE_URL}/user-workflows`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(workflowPayload),
    });
    if (!response.ok) throw new Error("Failed to save workflow");
    return response.json();
};

export const listWorkflows = async (): Promise<Workflow[]> => {
    const response = await fetch(`${API_BASE_URL}/user-workflows`, {
        headers: getHeaders(),
    });
    if (!response.ok) throw new Error("Failed to list workflows");
    return response.json();
};

export const getWorkflow = async (workflowId: string): Promise<Workflow> => {
    const response = await fetch(`${API_BASE_URL}/user-workflows/${workflowId}`, {
        headers: getHeaders(),
    });
    if (!response.ok) throw new Error("Workflow not found");
    return response.json();
};

export const runWorkflow = async (workflowId: string): Promise<void> => {
    const response = await fetch(`${API_BASE_URL}/user-workflows/${workflowId}/run`, {
        method: 'POST',
        headers: getHeaders(),
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to run workflow');
    }
}; 