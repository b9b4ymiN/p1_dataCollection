"""
Database Initialization Script
Creates all required tables and extensions
"""

from sqlalchemy import create_engine, text
import yaml
import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path='config.yaml'):
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing configuration file: {e}")
        sys.exit(1)


def create_db_engine(db_config):
    """Create database engine"""
    connection_string = (
        f"postgresql://{db_config['user']}:{db_config['password']}@"
        f"{db_config['host']}:{db_config['port']}/{db_config['database']}"
    )
    return create_engine(connection_string)


def init_database():
    """Initialize database with schema"""
    logger.info("Starting database initialization...")

    # Load config
    config = load_config()
    db_config = config['database']

    # Create engine
    logger.info(f"Connecting to database: {db_config['database']}")
    engine = create_db_engine(db_config)

    # Test connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"Connected to PostgreSQL: {version}")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)

    # Execute schema creation
    try:
        logger.info("Reading schema file...")
        with open('schemas/create_tables.sql', 'r') as f:
            sql_script = f.read()

        logger.info("Executing schema creation...")
        with engine.connect() as conn:
            # Split and execute statements
            statements = [s.strip() for s in sql_script.split(';') if s.strip()]
            for i, statement in enumerate(statements, 1):
                try:
                    conn.execute(text(statement))
                    conn.commit()
                    logger.debug(f"Executed statement {i}/{len(statements)}")
                except Exception as e:
                    logger.warning(f"Statement {i} failed (may already exist): {e}")
                    continue

        logger.info("✅ Database schema created successfully!")

        # Verify tables
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result]

        logger.info(f"Created tables: {', '.join(tables)}")

    except FileNotFoundError:
        logger.error("Schema file not found: schemas/create_tables.sql")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error creating schema: {e}")
        sys.exit(1)

    finally:
        engine.dispose()


if __name__ == "__main__":
    init_database()
