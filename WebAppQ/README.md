# 🌐 WebAppQ - Q Platform UI

## Overview

WebAppQ is the official web-based user interface for the Q Platform. It provides a simple, clean chat interface for users to interact with the platform's autonomous agents via the `H2M` service.

This application handles the full OIDC authentication flow with Keycloak and establishes a secure, real-time WebSocket connection to the backend. It can now handle both standard AI responses and direct clarification questions from an agent, providing a true human-in-the-loop experience.

## Tech Stack

-   **Framework**: React (with Create React App and TypeScript)
-   **UI Components**: Material-UI (MUI)
-   **Authentication**: `keycloak-js` library for OIDC integration.

---

## 🚀 Getting Started

### Prerequisites

-   Node.js and npm
-   A running instance of the Q Platform backend, including Keycloak and the `H2M` service.

### 1. Configure Keycloak

You must create a new client in your Keycloak realm for this web application.

-   **Realm**: `q-platform`
-   **Client ID**: `q-webapp`
-   **Client Protocol**: `openid-connect`
-   **Access Type**: `public`
-   **Valid Redirect URIs**: `http://localhost:3000/*` (or the address where you will run the app)
-   **Web Origins**: `http://localhost:3000`

### 2. Installation

Install the necessary dependencies.

```bash
# from within the WebAppQ/app directory
npm install
```

### 3. Running the Development Server

Start the local development server.

```bash
# from within the WebAppQ/app directory
npm start
```

The application will be available at `http://localhost:3000`. It will automatically redirect you to Keycloak to log in. 