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
    const [isWaitingForClarification, setIsWaitingForClarification] = useState(false);
    const [pendingWorkflowId, setPendingWorkflowId] = useState<string | null>(null);
    
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

            // Handle streamed thoughts
            if (receivedMessage.type === 'thought') {
                const thoughtMessage: Message = {
                    id: `thought-${Date.now()}-${Math.random()}`,
                    text: `Thinking: ${receivedMessage.text}`,
                    sender: 'thought',
                };
                setMessages(prev => [...prev, thoughtMessage]);
                return;
            }

            // Handle streamed response tokens
            if (receivedMessage.type === 'token') {
                setMessages(prevMessages => {
                    const lastMessage = prevMessages[prevMessages.length - 1];
                    // If the last message was from the agent, append the token
                    if (lastMessage && lastMessage.sender === 'agent') {
                        const updatedMessages = [...prevMessages];
                        updatedMessages[prevMessages.length - 1] = {
                            ...lastMessage,
                            text: lastMessage.text + receivedMessage.text,
                            conversation_id: receivedMessage.conversation_id
                        };
                        return updatedMessages;
                    } else {
                        // Otherwise, create a new agent message
                        const newMessage: Message = {
                            id: `agent-${Date.now()}`,
                            text: receivedMessage.text,
                            sender: 'agent',
                            conversation_id: receivedMessage.conversation_id,
                            feedback: null,
                        };
                        return [...prevMessages, newMessage];
                    }
                });
                
                // Set conversation ID if it's the first agent message
                if (receivedMessage.conversation_id && !conversationId) {
                    setConversationId(receivedMessage.conversation_id);
                }
                return;
            }

            // Handle end-of-stream or errors if needed
            if (receivedMessage.type === 'final' || receivedMessage.type === 'error') {
                console.log("Stream ended or error occurred:", receivedMessage.text);
                // Optionally, you could update the message state to indicate completion or error
            }
        };

        ws.current.onerror = (error) => console.error("WebSocket error:", error);
        ws.current.onclose = () => setIsConnected(false);

        return () => ws.current?.close();
    }, [authContext, conversationId]);

    const handleSendMessage = async () => {
        if (!input.trim() || !authContext?.token) return;

        const userMessage: Message = { id: `user-${Date.now()}`, text: input, sender: 'user' };
        setMessages(prev => [...prev, userMessage]);
        const currentInput = input;
        setInput('');

        // If waiting for clarification, send the answer to the specific endpoint
        if (isWaitingForClarification && pendingWorkflowId) {
            try {
                const res = await fetch(`http://localhost:8001/api/v1/goals/${pendingWorkflowId}/clarify`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authContext.token}` },
                    body: JSON.stringify({ answer: currentInput }),
                });
                const data = await res.json();
                if (res.ok) {
                    const agentMessage: Message = { id: `agent-${Date.now()}`, text: `Got it. A new workflow (${data.workflow_id}) has been created. I'll get started.`, sender: 'agent' };
                    setMessages(prev => [...prev, agentMessage]);
                } else {
                    throw new Error(data.detail?.message || "Failed to submit clarification.");
                }
            } catch (error: any) {
                const errorMessage: Message = { id: `agent-${Date.now()}`, text: `Error: ${error.message}`, sender: 'agent' };
                setMessages(prev => [...prev, errorMessage]);
            } finally {
                setIsWaitingForClarification(false);
                setPendingWorkflowId(null);
            }
            return;
        }

        // If it is a new prompt, send it to the task submission endpoint
        try {
            const response = await fetch('http://localhost:8001/api/v1/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authContext.token}` },
                body: JSON.stringify({ prompt: currentInput }),
            });
            const data = await response.json();

            if (response.ok) {
                 if (data.status === 'pending_clarification') {
                    const agentMessage: Message = { id: `agent-${Date.now()}`, text: data.clarifying_question, sender: 'agent' };
                    setMessages(prev => [...prev, agentMessage]);
                    setIsWaitingForClarification(true);
                    setPendingWorkflowId(data.workflow_id);
                } else {
                    const agentMessage: Message = { id: `agent-${Date.now()}`, text: `Workflow ${data.workflow_id} submitted with ${data.num_tasks} tasks.`, sender: 'agent' };
                    setMessages(prev => [...prev, agentMessage]);
                }
            } else {
                // If the API returns a 400 for ambiguity, it's now handled by the status code check above.
                // This will handle other errors.
                const errorDetail = data.detail?.message || JSON.stringify(data.detail);
                throw new Error(errorDetail);
            }
        } catch (error: any) {
            const errorMessage: Message = { id: `agent-${Date.now()}`, text: `Error: ${error.message}`, sender: 'agent' };
            setMessages(prev => [...prev, errorMessage]);
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
