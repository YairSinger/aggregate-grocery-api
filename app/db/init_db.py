from sqlalchemy import text
from app.db.session import engine
from app.db.models import Base

def init_db():
    with engine.connect() as conn:
        # Create PostGIS extension
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()
    
    # Create all tables
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Database initialized successfully.")
