"""
MongoDB Loader — 将数据写入 MongoDB

支持 upsert（存在则更新，不存在则插入），
通过指定唯一索引字段（symbol + date 或 symbol + report_period）实现去重。
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo import MongoClient, ReplaceOne
from pymongo.database import Database

from .base import BaseLoader, LoadResult

logger = logging.getLogger(__name__)


class MongoDBLoader(BaseLoader):
    """
    MongoDB 数据写入节点

    Args:
        connection_string: MongoDB 连接串
        db_name: 数据库名
        collection_name: 集合名
        unique_keys: 用于 upsert 判断的唯一键列表，默认 ["symbol", "report_period"]
    """

    def __init__(
        self,
        connection_string: str,
        db_name: str,
        collection_name: str,
        unique_keys: list[str] = None,
    ):
        self.connection_string = connection_string
        self.db_name = db_name
        self.collection_name = collection_name
        self.unique_keys = unique_keys or ["symbol", "report_period"]
        self._client: Optional[MongoClient] = None

    @property
    def target_type(self) -> str:
        return "mongodb"

    def _get_collection(self):
        if self._client is None:
            self._client = MongoClient(self.connection_string)
        db: Database = self._client[self.db_name]
        return db[self.collection_name]

    async def load(self, records: list[dict]) -> LoadResult:
        """批量 upsert 写入 MongoDB"""
        if not records:
            return LoadResult()

        result = LoadResult()
        now = datetime.now(timezone.utc)

        # 准备 upsert 操作
        operations = []
        for record in records:
            # 添加元数据
            record["updated_at"] = now
            if "created_at" not in record:
                record["created_at"] = now

            # 构建 filter（唯一键匹配）
            filter_dict = {k: record.get(k) for k in self.unique_keys if record.get(k) is not None}
            if not filter_dict:
                result.skipped += 1
                result.add_error(record, "缺少唯一键字段")
                continue

            operations.append(
                ReplaceOne(
                    filter_dict,
                    record,
                    upsert=True,
                )
            )

        if not operations:
            return result

        # 执行批量写入
        collection = self._get_collection()
        try:
            response = collection.bulk_write(operations, ordered=False)
            result.inserted = response.upserted_count
            result.updated = response.modified_count
            result.skipped += len(operations) - result.inserted - result.updated
            logger.info(
                f"MongoDB bulk write: upserted={result.inserted}, "
                f"modified={result.updated}, skipped={result.skipped}"
            )
        except Exception as e:
            logger.error(f"MongoDB bulk write error: {e}")
            for record in records:
                result.add_error(record, str(e))

        return result

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
