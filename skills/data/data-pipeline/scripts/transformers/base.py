"""数据清洗转换节点基类"""
from abc import ABC, abstractmethod
from typing import Any


class BaseTransformer(ABC):
    """所有数据清洗转换节点的基类"""

    @abstractmethod
    async def transform(self, records: list[dict]) -> list[dict]:
        """
        对 records 进行清洗转换

        Args:
            records: 原始记录列表

        Returns:
            清洗后的记录列表（数量应与输入一致）
            异常记录可保留但标记，或直接过滤
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"
