import os

from alembic import context
from app.models.entities import Base
from sqlalchemy import create_engine

engine = create_engine(os.environ["AUTONOMY_DATABASE_URL"])
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
