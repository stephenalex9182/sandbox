# Database schema

The application currently creates the SQLAlchemy schema from the model metadata at startup (`Base.metadata.create_all`). For production, introduce Alembic revisions before evolving deployed schemas; `create_all` does not alter existing tables.
