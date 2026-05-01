"""数据加载节点基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LoadResult:
    """数据加载结果"""
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[dict] = field(default_factory=list)

    def add_error(self, record: dict, reason: str):
        self.errors.append({"record": record, "reason": reason})

    @property
    def total_processed(self) -> int:
        return self.inserted + self.updated + self.skipped + len(self.errors)


class BaseLoader(ABC):
    """所有数据加载节点的基类"""

    @property
    @abstractmethod
    def target_type(self) -> str:
        """目标存储类型，如 'mongodb', 'csv', 'api'"""
        pass

    @abstractmethod
    async def load(self, records: list[dict]) -> LoadResult:
        """
        执行数据加载

        Args:
            records: 待加载的记录列表

        Returns:
            LoadResult，包含插入/更新/跳过/错误计数
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} target_type='{self.target_type}'>"
