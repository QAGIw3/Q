// WebAppQ/app/src/components/Dashboard/shared.ts
export const connectToObservabilitySocket = (onMessage: (data: any) => void) => {
    const wsUrl = (process.env.REACT_APP_MANAGERQ_API_URL || 'http://localhost:8000').replace('http', 'ws') + '/v1/observability/ws';
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
        onMessage(JSON.parse(event.data));
    };
    return ws;
}; 