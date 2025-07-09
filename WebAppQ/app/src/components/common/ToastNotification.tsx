// WebAppQ/app/src/components/common/ToastNotification.tsx
import React from 'react';
import { Snackbar, Alert, AlertTitle } from '@mui/material';

interface ToastNotificationProps {
    open: boolean;
    onClose: () => void;
    message: string;
    title: string;
    severity?: 'success' | 'info' | 'warning' | 'error';
}

export const ToastNotification: React.FC<ToastNotificationProps> = ({ open, onClose, message, title, severity = 'info' }) => {
    return (
        <Snackbar
            open={open}
            autoHideDuration={6000}
            onClose={onClose}
            anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
            <Alert onClose={onClose} severity={severity} sx={{ width: '100%' }}>
                <AlertTitle>{title}</AlertTitle>
                {message}
            </Alert>
        </Snackbar>
    );
}; 