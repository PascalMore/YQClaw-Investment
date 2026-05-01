"""数据采集节点基类"""
from abc import ABC, abstractmethod
from typing import Any


class BaseExtractor(ABC):
    """所有数据采集节点的基类"""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """
        数据来源标识
        如: 'tushare', 'akshare', 'image', 'csv', 'telegram_message', 'feishu_message'
        """
        pass

    @abstractmethod
    async def extract(self, source: Any, **kwargs) -> list[dict]:
        """
        执行采集

        Args:
            source: 数据来源（图片路径/URL、API 参数、文件路径等）
            **kwargs: 扩展参数

        Returns:
            结构化数据列表，每条记录为一个 dict
            返回空列表表示采集成功但无数据
            抛出异常表示采集失败
        """
        pass

    @abstractmethod
    async def validate_source(self, source: Any) -> bool:
        """
        校验数据来源是否有效

        Args:
            source: 数据来源对象

        Returns:
            True = 有效，False = 无效
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} source_type='{self.source_type}'>"
