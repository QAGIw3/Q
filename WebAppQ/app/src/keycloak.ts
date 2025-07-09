// WebAppQ/app/src/keycloak.ts
import Keycloak from 'keycloak-js';

// The configuration would typically come from environment variables
// or a configuration service, not be hardcoded.
const keycloakConfig = {
    realm: process.env.REACT_APP_KEYCLOAK_REALM || 'QPlatformRealm',
    url: process.env.REACT_APP_KEYCLOAK_URL || 'http://localhost:8080/auth',
    clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID || 'webapp-q-client',
};

const keycloak = new Keycloak(keycloakConfig);

export default keycloak; 