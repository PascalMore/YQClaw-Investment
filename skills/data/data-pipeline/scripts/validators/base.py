"""数据校验节点基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationResult:
    """校验结果容器"""
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str):
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str):
        self.warnings.append(message)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


class BaseValidator(ABC):
    """所有数据校验节点的基类"""

    @abstractmethod
    async def validate(self, records: list[dict]) -> ValidationResult:
        """
        对记录进行校验

        Args:
            records: 待校验的记录列表

        Returns:
            ValidationResult，包含校验是否通过及错误/警告信息
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"
