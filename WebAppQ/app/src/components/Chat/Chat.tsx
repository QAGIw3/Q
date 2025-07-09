import React, { useState, useEffect, useRef, useContext } from 'react';
import { AuthContext } from '../../AuthContext';
import './Chat.css';

interface Message {
    text: string;
    sender: 'user' | 'agent';
    conversation_id?: string;
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

        // TODO: Make the WebSocket URL configurable
        const wsUrl = `ws://localhost:8002/api/v1/chat/ws?token=${authContext.token}`;
        ws.current = new WebSocket(wsUrl);

        ws.current.onopen = () => {
            console.log("WebSocket connected");
            setIsConnected(true);
        };

        ws.current.onmessage = (event) => {
            const receivedMessage = JSON.parse(event.data);
            setMessages(prev => [...prev, { text: receivedMessage.text, sender: 'agent' }]);
            if (receivedMessage.conversation_id && !conversationId) {
                setConversationId(receivedMessage.conversation_id);
            }
        };

        ws.current.onerror = (error) => {
            console.error("WebSocket error:", error);
        };

        ws.current.onclose = () => {
            console.log("WebSocket disconnected");
            setIsConnected(false);
        };

        // Cleanup on component unmount
        return () => {
            ws.current?.close();
        };
    }, [authContext, conversationId]); // Reconnect if token changes

    const sendMessage = () => {
        if (input.trim() && ws.current && ws.current.readyState === WebSocket.OPEN) {
            const messagePayload = {
                text: input,
                conversation_id: conversationId,
            };
            ws.current.send(JSON.stringify(messagePayload));
            setMessages(prev => [...prev, { text: input, sender: 'user' }]);
            setInput('');
        }
    };

    return (
        <div className="chat-container">
            <div className="connection-status">
                Status: {isConnected ? <span className="connected">Connected</span> : <span className="disconnected">Disconnected</span>}
            </div>
            <div className="message-window">
                {messages.map((msg, index) => (
                    <div key={index} className={`message ${msg.sender}`}>
                        {msg.text}
                    </div>
                ))}
            </div>
            <div className="input-area">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                    placeholder="Type your message..."
                    disabled={!isConnected}
                />
                <button onClick={sendMessage} disabled={!isConnected}>Send</button>
            </div>
        </div>
    );
};

export default Chat;
