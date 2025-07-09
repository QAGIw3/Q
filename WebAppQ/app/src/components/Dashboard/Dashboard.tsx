import React, { useState, useEffect, useContext, useRef } from 'react';
import { AuthContext } from '../../AuthContext';
import './Dashboard.css';
import WorkflowVisualizer from '../WorkflowVisualizer/WorkflowVisualizer';
import { useSearchParams } from 'react-router-dom';

interface Anomaly {
    id: string;
    service_name: string;
    message: string;
    timestamp: string;
    workflow_id?: string;
    workflow?: Workflow;
}

interface Workflow {
    id: string;
    tasks: Record<string, WorkflowTask>;
}

interface WorkflowTask {
    id: string;
    status: string;
    result?: string;
}

export const Dashboard: React.FC = () => {
    const [anomalies, setAnomalies] = useState<Record<string, Anomaly>>({});
    const [selectedAnomalyId, setSelectedAnomalyId] = useState<string | null>(null);
    const [connectionStatus, setConnectionStatus] = useState<'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED' | 'RECONNECTING'>('CONNECTING');
    const authContext = useContext(AuthContext);
    const [searchParams] = useSearchParams();
    const ws = useRef<WebSocket | null>(null);
    const reconnectInterval = useRef<NodeJS.Timeout | null>(null);

    const connect = () => {
        if (!authContext?.token) return;

        const wsUrl = `ws://localhost:8001/v1/dashboard/ws`; // Corrected port
        ws.current = new WebSocket(wsUrl);
        setConnectionStatus('CONNECTING');

        ws.current.onopen = () => {
            console.log("Dashboard WebSocket connected");
            setConnectionStatus('OPEN');
            if (reconnectInterval.current) {
                clearInterval(reconnectInterval.current);
                reconnectInterval.current = null;
            }
        };

        ws.current.onclose = () => {
            console.log("Dashboard WebSocket disconnected");
            setConnectionStatus('CLOSED');
            if (!reconnectInterval.current) {
                reconnectInterval.current = setInterval(() => {
                    setConnectionStatus('RECONNECTING');
                    connect();
                }, 5000);
            }
        };

        ws.current.onerror = (err) => {
            console.error("Dashboard WebSocket error:", err);
            ws.current?.close();
        };

        ws.current.onmessage = (event) => {
            const message = JSON.parse(event.data);
            
            if (message.event_type === 'anomaly_detected') {
                const anomalyData = message.data.payload;
                const newAnomaly: Anomaly = {
                    id: message.data.event_id,
                    service_name: anomalyData.service_name,
                    message: anomalyData.message,
                    timestamp: message.data.timestamp,
                    workflow_id: anomalyData.workflow_id, // Assuming the event contains this
                };
                setAnomalies(prev => ({ ...prev, [newAnomaly.id]: newAnomaly }));
            }
            
            if (message.event_type === 'workflow_task_updated') {
                const update = message.data;
                // This part is tricky without knowing the anomaly an update belongs to.
                // A better event design would link workflow_id to an anomaly_id.
                // For now, we'll have to find which anomaly to update, or ignore.
                // This part would need to be improved in a real system.
            }
        };
    };

    useEffect(() => {
        const workflowIdFromUrl = searchParams.get('workflow_id');
        if (workflowIdFromUrl) {
            // Find the anomaly that has this workflow_id
            const anomaly = Object.values(anomalies).find(a => a.workflow_id === workflowIdFromUrl);
            if (anomaly) {
                setSelectedAnomalyId(anomaly.id);
            }
        }
    }, [searchParams, anomalies]);

    useEffect(() => {
        connect();
        return () => {
            if (reconnectInterval.current) clearInterval(reconnectInterval.current);
            ws.current?.close();
        };
    }, [authContext]);

    const selectedAnomaly = selectedAnomalyId ? anomalies[selectedAnomalyId] : null;

    return (
        <div className="dashboard-container">
            <div className={`connection-status ${connectionStatus.toLowerCase()}`}>
                Dashboard Status: {connectionStatus}
            </div>
            <div className="anomaly-list-panel">
                <h2>Active Anomalies</h2>
                <ul>
                    {Object.values(anomalies).map(anom => (
                        <li key={anom.id} onClick={() => setSelectedAnomalyId(anom.id)}>
                            <strong>{anom.service_name}</strong>
                            <p>{anom.message}</p>
                            <small>{new Date(anom.timestamp).toLocaleString()}</small>
                        </li>
                    ))}
                </ul>
            </div>
            <div className="workflow-detail-panel">
                <h2>Investigation Details</h2>
                {selectedAnomaly ? (
                    <div>
                        <h3>{selectedAnomaly.service_name}</h3>
                        <p>{selectedAnomaly.message}</p>
                        {selectedAnomaly.workflow_id && (
                            <WorkflowVisualizer workflowId={selectedAnomaly.workflow_id} />
                        )}
                    </div>
                ) : (
                    <p>Select an anomaly to view details.</p>
                )}
            </div>
        </div>
    );
}; 