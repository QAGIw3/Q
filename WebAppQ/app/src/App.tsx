import React, { useState, useEffect, useRef, useContext } from 'react';
import { Box, TextField, Button, Paper, Typography, AppBar, Toolbar, CircularProgress, Container } from '@mui/material';
import { AuthContext } from './AuthContext';
import { jwtDecode } from 'jwt-decode';

interface Message {
  sender: 'user' | 'ai';
  text: string;
}

function App() {
  const authContext = useContext(AuthContext);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (authContext?.isAuthenticated && authContext.token) {
      // The token from keycloak is the JWT. We need the payload for the ws query.
      const decoded: any = jwtDecode(authContext.token);
      const claimsBase64 = btoa(JSON.stringify(decoded));
      
      const wsUrl = `ws://localhost:8002/chat/ws?claims=${claimsBase64}`;
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => console.log("WebSocket connected");
      ws.current.onclose = () => console.log("WebSocket disconnected");

      ws.current.onmessage = (event) => {
        const receivedMessage = JSON.parse(event.data);
        setMessages((prev) => [...prev, { sender: 'ai', text: receivedMessage.text }]);
        if (receivedMessage.conversation_id) {
          setConversationId(receivedMessage.conversation_id);
        }
      };

      return () => {
        ws.current?.close();
      };
    }
  }, [authContext?.isAuthenticated, authContext?.token]);

  const handleSend = () => {
    if (input.trim() && ws.current?.readyState === WebSocket.OPEN) {
      const message = {
        text: input,
        conversation_id: conversationId,
      };
      ws.current.send(JSON.stringify(message));
      setMessages((prev) => [...prev, { sender: 'user', text: input }]);
      setInput('');
    }
  };

  if (!authContext?.isAuthenticated) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100vh">
        <CircularProgress />
        <Typography ml={2}>Authenticating...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', bgcolor: '#f5f5f5' }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Q Platform Chat
          </Typography>
          <Button color="inherit" onClick={authContext.logout}>Logout</Button>
        </Toolbar>
      </AppBar>
      <Container maxWidth="md" sx={{ flexGrow: 1, py: 2 }}>
        <Paper elevation={3} sx={{ height: 'calc(100vh - 200px)', overflowY: 'auto', p: 2, display: 'flex', flexDirection: 'column-reverse' }}>
          {/* Messages will be reversed in CSS, so map normally */}
          <Box>
            {messages.map((msg, index) => (
              <Box key={index} my={1} display="flex" justifyContent={msg.sender === 'user' ? 'flex-end' : 'flex-start'}>
                <Paper elevation={1} sx={{ p: 1.5, bgcolor: msg.sender === 'user' ? 'primary.main' : 'grey.300', color: msg.sender === 'user' ? 'primary.contrastText' : 'inherit', maxWidth: '70%' }}>
                  <Typography variant="body1">{msg.text}</Typography>
                </Paper>
              </Box>
            ))}
          </Box>
        </Paper>
        <Box component="form" sx={{ mt: 2, display: 'flex' }} onSubmit={(e) => { e.preventDefault(); handleSend(); }}>
          <TextField
            fullWidth
            variant="outlined"
            placeholder="Type a message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <Button type="submit" variant="contained" color="primary" sx={{ ml: 1, px: 4 }}>
            Send
          </Button>
        </Box>
      </Container>
    </Box>
  );
}

export default App;
