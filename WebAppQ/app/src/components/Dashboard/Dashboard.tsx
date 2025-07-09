import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../../AuthContext';
import './Dashboard.css';
import WorkflowVisualizer from '../WorkflowVisualizer/WorkflowVisualizer';

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
    const authContext = useContext(AuthContext);

    useEffect(() => {
        if (!authContext || !authContext.token) return;

        const wsUrl = `ws://localhost:8004/v1/dashboard/ws`; // managerQ runs on 8004
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => console.log("Dashboard WebSocket connected");
        ws.onclose = () => console.log("Dashboard WebSocket disconnected");
        ws.onerror = (err) => console.error("Dashboard WebSocket error:", err);

        ws.onmessage = (event) => {
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

        return () => ws.close();
    }, [authContext]);

    const selectedAnomaly = selectedAnomalyId ? anomalies[selectedAnomalyId] : null;

    return (
        <div className="dashboard-container">
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