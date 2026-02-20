"""MongoDB adapter — UoW, repository, outbox, event store.

Requires the ``mongodb`` extra::

    pip install "mp-commons[mongodb]"
"""

from mp_commons.adapters.mongodb.event_store import MongoEventStore
from mp_commons.adapters.mongodb.outbox import MongoOutboxStore
from mp_commons.adapters.mongodb.repository import MongoRepository
from mp_commons.adapters.mongodb.uow import MongoUnitOfWork

__all__ = [
    "MongoEventStore",
    "MongoOutboxStore",
    "MongoRepository",
    "MongoUnitOfWork",
]
