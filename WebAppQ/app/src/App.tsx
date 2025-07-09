import React, { useContext } from 'react';
import { BrowserRouter as Router, Route, Routes, Link, Navigate } from 'react-router-dom';
import { Box, Typography, AppBar, Toolbar, Button, CircularProgress, Container } from '@mui/material';
import { AuthContext, AuthProvider } from './AuthContext';
import Chat from './components/Chat/Chat';

function Home() {
  return (
    <Container maxWidth="md" sx={{ textAlign: 'center', mt: 8 }}>
      <Typography variant="h2" component="h1" gutterBottom>
        Welcome to the Q Platform
      </Typography>
      <Typography variant="h5">
        An advanced, AI-powered platform for the future.
      </Typography>
    </Container>
  );
}

function App() {
  const authContext = useContext(AuthContext);

  if (!authContext?.isAuthenticated) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100vh">
        <CircularProgress />
        <Typography ml={2}>Authenticating...</Typography>
      </Box>
    );
  }

  return (
    <Router>
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', bgcolor: '#f5f5f5' }}>
        <AppBar position="static">
          <Toolbar>
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              <Link to="/" style={{ textDecoration: 'none', color: 'inherit' }}>Q Platform</Link>
            </Typography>
            <Button color="inherit" component={Link} to="/chat">Chat</Button>
            <Button color="inherit" onClick={authContext.logout}>Logout</Button>
          </Toolbar>
        </AppBar>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/chat" element={
            <RequireAuth>
              <Chat />
            </RequireAuth>
          } />
        </Routes>
      </Box>
    </Router>
  );
}

function RequireAuth({ children }: { children: JSX.Element }) {
  const authContext = useContext(AuthContext);
  if (!authContext || !authContext.isAuthenticated) {
    return <Navigate to="/" replace />;
  }
  return children;
}

// Wrap App with AuthProvider
const AppWithAuth = () => (
  <AuthProvider>
    <App />
  </AuthProvider>
);

export default AppWithAuth;
