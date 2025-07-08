import Keycloak from 'keycloak-js';

const keycloak = new Keycloak({
  url: 'http://localhost:8080/', // Your Keycloak server URL
  realm: 'q-platform',
  clientId: 'q-webapp', // The client ID you will create in Keycloak
});

export default keycloak; 