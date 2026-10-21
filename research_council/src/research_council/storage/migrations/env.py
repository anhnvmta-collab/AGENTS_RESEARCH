from alembic import context

from research_council.storage.database import metadata

connection = context.config.attributes["connection"]
context.configure(connection=connection, target_metadata=metadata, compare_type=True)
with context.begin_transaction():
    context.run_migrations()
