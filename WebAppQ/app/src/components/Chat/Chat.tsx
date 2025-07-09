import React, { useState, useEffect, useRef, useContext } from 'react';
import { AuthContext } from '../../AuthContext';
import './Chat.css';
import { UITableComponent } from './UITable';

interface Message {
    id: string;
    text: string;
    sender: 'user' | 'agent' | 'thought';
    conversation_id?: string;
    feedback?: 'good' | 'bad' | null;
    ui_component?: any;
}

const Chat: React.FC = () => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [conversationId, setConversationId] = useState<string | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    
    const authContext = useContext(AuthContext);
    const ws = useRef<WebSocket | null>(null);

    useEffect(() => {
        if (!authContext || !authContext.token) {
            console.error("No auth token available for WebSocket connection.");
            return;
        }

        const wsUrl = `ws://localhost:8002/api/v1/chat/ws?token=${authContext.token}`;
        ws.current = new WebSocket(wsUrl);

        ws.current.onopen = () => setIsConnected(true);

        ws.current.onmessage = (event) => {
            const receivedMessage = JSON.parse(event.data);

            if (receivedMessage.type === 'thought') {
                const thoughtMessage: Message = {
                    id: `thought-${Date.now()}-${Math.random()}`,
                    text: `Thinking: ${receivedMessage.text}`, // Add a prefix for clarity
                    sender: 'thought',
                };
                setMessages(prev => [...prev, thoughtMessage]);
                return; // Don't process as a regular agent message
            }

            let uiComponent = null;

            try {
                const potentialUI = JSON.parse(receivedMessage.text);
                if (potentialUI.ui_component) {
                    uiComponent = potentialUI;
                }
            } catch (e) {
                // Not a UI component, treat as plain text
            }

            const agentMessage: Message = {
                id: `agent-${Date.now()}-${Math.random()}`,
                text: receivedMessage.text,
                sender: 'agent',
                conversation_id: receivedMessage.conversation_id,
                feedback: null,
                ui_component: uiComponent,
            };
            setMessages(prev => [...prev, agentMessage]);
            if (receivedMessage.conversation_id && !conversationId) {
                setConversationId(receivedMessage.conversation_id);
            }
        };

        ws.current.onerror = (error) => console.error("WebSocket error:", error);
        ws.current.onclose = () => setIsConnected(false);

        return () => ws.current?.close();
    }, [authContext, conversationId]);

    const handleSendMessage = () => {
        if (input.trim() && ws.current?.readyState === WebSocket.OPEN) {
            const userMessage: Message = {
                id: `user-${Date.now()}`,
                text: input,
                sender: 'user',
            };
            const payload = {
                text: input,
                conversation_id: conversationId,
            };
            ws.current.send(JSON.stringify(payload));
            setMessages(prev => [...prev, userMessage]);
            setInput('');
        }
    };

    const handleSendFeedback = async (messageId: string, feedback: 'good' | 'bad') => {
        const message = messages.find(m => m.id === messageId);
        if (!message || !authContext?.token) return;

        console.log(`Sending feedback for message ${messageId}: ${feedback}`);

        try {
            const response = await fetch('http://localhost:8002/api/v1/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authContext.token}`,
                },
                body: JSON.stringify({
                    message_id: message.id,
                    conversation_id: message.conversation_id,
                    feedback: feedback,
                    text: message.text,
                }),
            });

            if (response.ok) {
                setMessages(prev => prev.map(m => 
                    m.id === messageId ? { ...m, feedback } : m
                ));
            } else {
                console.error('Failed to submit feedback:', response.statusText);
            }
        } catch (error) {
            console.error('Error submitting feedback:', error);
        }
    };

    return (
        <div className="chat-container">
            <div className="connection-status">
                Status: {isConnected ? <span className="connected">Connected</span> : <span className="disconnected">Connected</span>}
            </div>
            <div className="message-window">
                {messages.map((msg) => (
                    <div key={msg.id} className={`message ${msg.sender}`}>
                        {msg.ui_component ? (
                            <DynamicUIComponent component={msg.ui_component} />
                        ) : (
                            <div className="message-text">{msg.text}</div>
                        )}
                        
                        {msg.sender === 'agent' && (
                            <div className="feedback-buttons">
                                <button 
                                    onClick={() => handleSendFeedback(msg.id, 'good')}
                                    disabled={msg.feedback !== null}
                                    className={msg.feedback === 'good' ? 'selected' : ''}
                                >
                                    👍
                                </button>
                                <button 
                                    onClick={() => handleSendFeedback(msg.id, 'bad')}
                                    disabled={msg.feedback !== null}
                                    className={msg.feedback === 'bad' ? 'selected' : ''}
                                >
                                    👎
                                </button>
                            </div>
                        )}
                    </div>
                ))}
            </div>
            <div className="input-area">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                    placeholder="Type your message..."
                    disabled={!isConnected}
                />
                <button onClick={handleSendMessage} disabled={!isConnected}>Send</button>
            </div>
        </div>
    );
};

// A helper component to select the correct renderer
const DynamicUIComponent: React.FC<{ component: any }> = ({ component }) => {
    switch (component.ui_component) {
        case 'table':
            return <UITableComponent headers={component.headers} rows={component.rows} />;
        default:
            return <div className="message-text">{JSON.stringify(component)}</div>;
    }
};

export default Chat;
