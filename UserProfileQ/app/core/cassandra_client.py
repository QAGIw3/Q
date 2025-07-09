# UserProfileQ/app/core/cassandra_client.py
import logging
from cassandra.cluster import Cluster
from cassandra.cqlengine import connection
from cassandra.cqlengine.management import sync_table
from UserProfileQ.app.models.profile import ProfileModel

logger = logging.getLogger(__name__)

class CassandraClient:
    def __init__(self, hosts, keyspace):
        self.hosts = hosts
        self.keyspace = keyspace
        self.session = None
        self.cluster = None

    def connect(self):
        try:
            self.cluster = Cluster(self.hosts)
            self.session = self.cluster.connect()
            
            # Create keyspace if it doesn't exist
            self.session.execute(f"""
                CREATE KEYSPACE IF NOT EXISTS {self.keyspace}
                WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': '1'}}
                AND durable_writes = true;
            """)
            
            self.session.set_keyspace(self.keyspace)
            connection.set_session(self.session)
            
            logger.info(f"Connected to Cassandra and set keyspace to '{self.keyspace}'.")
            
            # Sync the model with the database schema
            sync_table(ProfileModel)
            logger.info("Synced ProfileModel table with Cassandra.")

        except Exception as e:
            logger.error(f"Failed to connect to Cassandra or sync table: {e}", exc_info=True)
            raise

    def close(self):
        if self.cluster:
            self.cluster.shutdown()
            logger.info("Cassandra connection closed.")

# Instantiate a client for the application to use
# This will be configured properly in the main application file
cassandra_client = None 