# skills/data/data_interface/mongo_writer.py
"""MongoDB writer implementation."""

import os
import logging
from datetime import datetime
from typing import List, Dict, Optional

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

from .base_writer import IWriter

# Load .env from workspace root
load_dotenv('/home/pascal/.openclaw/workspace-yquant/.env')

logger = logging.getLogger(__name__)


class MongoWriter(IWriter):
    """MongoDB write implementation implementing IWriter interface."""
    
    _client: Optional[MongoClient] = None
    
    def __init__(self, connection_string: str = None, database: str = 'tradingagents'):
        """Initialize MongoDB writer.
        
        Args:
            connection_string: MongoDB connection string (reads from env if not provided)
            database: Database name, default 'tradingagents'
        """
        if connection_string is None:
            connection_string = os.getenv('MONGODB_CONNECTION_STRING')
            if connection_string is None:
                host = os.getenv('MONGODB_HOST', '172.25.240.1')
                port = os.getenv('MONGODB_PORT', '27017')
                username = os.getenv('MONGODB_USERNAME', '')
                password = os.getenv('MONGODB_PASSWORD', '')
                if username and password:
                    connection_string = f"mongodb://{username}:{password}@{host}:{port}/admin"
                else:
                    connection_string = f"mongodb://{host}:{port}/"
        
        if MongoWriter._client is None:
            MongoWriter._client = MongoClient(connection_string)
        
        self.db = MongoWriter._client[database]
        self.database = database
    
    def write(self, data: List[Dict], **kwargs) -> int:
        """Write data to collection.
        
        Args:
            data: List of data records to write
            **kwargs: Optional params - collection_name
        
        Returns:
            int: Number of records written
        """
        if not data:
            return 0
        
        collection_name = kwargs.get('collection_name', 'portfolio_position')
        collection = self.db[collection_name]
        records = [self._with_created_at(record) for record in data]
        
        result = collection.insert_many(records, ordered=False)
        count = len(result.inserted_ids)
        
        logger.info(f"[MongoWriter] wrote {count} records to {collection_name}")
        return count
    
    def upsert(self, data: List[Dict], **kwargs) -> int:
        """Upsert data based on unique keys.
        
        Args:
            data: List of data records to upsert
            **kwargs: Optional params - collection_name, unique_keys
        
        Returns:
            int: Number of records affected
        """
        if not data:
            return 0
        
        collection_name = kwargs.get('collection_name', 'portfolio_position')
        unique_keys = kwargs.get('unique_keys', ['product_code', 'position_date'])
        collection = self.db[collection_name]
        
        operations = []
        for record in data:
            # Build filter from unique keys
            filter_dict = {k: record[k] for k in unique_keys if k in record}
            if not filter_dict:
                continue
            record = self._with_created_at(record)
            set_fields = dict(record)
            created_at = set_fields.pop('created_at')
            operations.append(
                UpdateOne(
                    filter_dict,
                    {'$set': set_fields, '$setOnInsert': {'created_at': created_at}},
                    upsert=True,
                )
            )
        
        if operations:
            result = collection.bulk_write(operations, ordered=False)
            count = result.matched_count + result.upserted_count
            logger.info(f"[MongoWriter] upserted {count} records to {collection_name}")
            return count
        
        return 0

    def write_argus_credential_scores(self, data: List[Dict]) -> int:
        """Upsert Argus product credibility scores into the Phase 2 raw table."""
        return self.upsert(
            data,
            collection_name='08_research_argus_credential_score',
            unique_keys=['date', 'product_code'],
        )

    def write_argus_signals(self, data: List[Dict]) -> int:
        """Upsert Argus daily signals into the Phase 2 raw signal table."""
        return self.upsert(
            data,
            collection_name='08_research_argus_signal',
            unique_keys=['date', 'signal_id'],
        )

    def write_argus_stock_pool(self, data: List[Dict]) -> int:
        """Upsert Argus four-zone stock pool state into the Phase 2 raw table."""
        return self.upsert(
            data,
            collection_name='08_research_argus_stock_pool',
            unique_keys=['date', 'wind_code'],
        )

    def ensure_argus_indexes(self) -> None:
        """Create idempotent indexes for Argus Phase 2 output collections."""
        index_specs = {
            '08_research_argus_credential_score': [('date', 1), ('product_code', 1)],
            '08_research_argus_signal': [('date', 1), ('signal_id', 1)],
            '08_research_argus_stock_pool': [('date', 1), ('wind_code', 1)],
        }
        for collection_name, keys in index_specs.items():
            self.db[collection_name].create_index(keys, unique=True)

    @staticmethod
    def _with_created_at(record: Dict) -> Dict:
        enriched = dict(record)
        enriched.setdefault('created_at', datetime.now().isoformat())
        return enriched
    
    @classmethod
    def close(cls):
        """Close MongoDB client connection."""
        if cls._client is not None:
            cls._client.close()
            cls._client = None
