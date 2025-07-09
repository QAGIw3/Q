import React, { useContext, useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, Link, Navigate, useLocation } from 'react-router-dom';
import { Box, Typography, AppBar, Toolbar, Button, CircularProgress, Container } from '@mui/material';
import { AuthContext, AuthProvider } from './AuthContext';
import Chat from './components/Chat/Chat';
import { WorkflowsPage } from './pages/WorkflowsPage';
import { WorkflowDetailPage } from './pages/WorkflowDetailPage';
import { SearchPage } from './pages/SearchPage';
import { RegisterPage } from './pages/RegisterPage';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { ToastNotification } from './components/common/ToastNotification';
import { connectToDashboardSocket, disconnectFromDashboardSocket } from './services/managerAPI';

function Home() {
  const authContext = useContext(AuthContext);
  return (
    <Container maxWidth="md" sx={{ textAlign: 'center', mt: 8 }}>
      <Typography variant="h2" component="h1" gutterBottom>
        Welcome to the Q Platform
      </Typography>
      <Typography variant="h5" sx={{ mb: 4 }}>
        An advanced, AI-powered platform for the future.
      </Typography>
      {!authContext?.isAuthenticated && (
        <Box>
            <Button variant="contained" size="large" onClick={() => authContext?.login()}>Login</Button>
            <Button variant="outlined" size="large" component={Link} to="/register" sx={{ ml: 2 }}>Register</Button>
        </Box>
      )}
    </Container>
  );
}

function App() {
  const authContext = useContext(AuthContext);
  const [toast, setToast] = useState<{ open: boolean, message: string, title: string }>({ open: false, message: '', title: '' });

  useEffect(() => {
      if (authContext?.isAuthenticated) {
          const handleSocketMessage = (data: any) => {
              if (data.event_type === "APPROVAL_REQUIRED") {
                  setToast({
                      open: true,
                      title: "Action Required",
                      message: `An approval is waiting for you: ${data.data.message}`
                  });
              }
          };
          connectToDashboardSocket(handleSocketMessage);
      }
      return () => {
          disconnectFromDashboardSocket();
      };
  }, [authContext]);

  const handleCloseToast = () => {
      setToast({ ...toast, open: false });
  };

  if (!authContext?.isAuthenticated) {
    // This is shown while the Keycloak adapter initializes.
    // If the user is not logged in, they will be redirected by Keycloak.
    // If they are logged in, the app will render.
    return (
      <Box display="flex" justifyContent="center" alignItems="center" height="100vh">
        <CircularProgress />
        <Typography ml={2}>Loading...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', bgcolor: '#f5f5f5' }}>
      <ToastNotification
          open={toast.open}
          onClose={handleCloseToast}
          title={toast.title}
          message={toast.message}
      />
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            <Link to="/" style={{ textDecoration: 'none', color: 'inherit' }}>Q Platform</Link>
          </Typography>
          <Button color="inherit" component={Link} to="/chat">Chat</Button>
          <Button color="inherit" component={Link} to="/workflows">Workflows</Button>
          <Button color="inherit" component={Link} to="/search">Search</Button>
          <Button color="inherit" component={Link} to="/approvals">Approvals</Button>
          <Button color="inherit" onClick={() => authContext.logout && authContext.logout()}>Logout</Button>
        </Toolbar>
      </AppBar>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/approvals" element={<RequireAuth><ApprovalsPage /></RequireAuth>} />
        <Route path="/chat" element={<RequireAuth><Chat /></RequireAuth>} />
        <Route path="/workflows" element={<RequireAuth><WorkflowsPage /></RequireAuth>} />
        <Route path="/workflows/:workflowId" element={<RequireAuth><WorkflowDetailPage /></RequireAuth>} />
        <Route path="/search" element={<RequireAuth><SearchPage /></RequireAuth>} />
      </Routes>
    </Box>
  );
}

function RequireAuth({ children }: { children: React.ReactElement }) {
  const authContext = useContext(AuthContext);
  const location = useLocation();

  if (!authContext?.isAuthenticated) {
    // Redirect them to the / page, but save the current location they were
    // trying to go to. This allows us to send them along to that page after they
    // log in, which is a common UX pattern.
    return <Navigate to="/" state={{ from: location }} replace />;
  }
  return children;
}

// Wrap the entire app logic in the Router
const AppContainer = () => (
    <Router>
        <App />
    </Router>
)

// Wrap App with AuthProvider
const AppWithAuth = () => (
  <AuthProvider>
    <AppContainer />
  </AuthProvider>
);

export default AppWithAuth;
