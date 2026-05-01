"""
DataPipeline — 统一数据管道引擎

将 Extractor → Transformer → Validator → Loader 串联执行，
实现任何来源数据的标准化处理流程。
"""
import logging
from typing import Any

from .extractors.base import BaseExtractor
from .transformers.base import BaseTransformer
from .validators.base import BaseValidator, ValidationResult
from .loaders.base import BaseLoader, LoadResult

logger = logging.getLogger(__name__)


class DataPipeline:
    """
    统一数据管道引擎

    典型用法:
        pipeline = DataPipeline(
            extractor=ImageParserExtractor(),
            transformer=NaNNormalizer(),
            validator=SchemaValidator(schema_name="manual_input"),
            loader=MongoDBLoader(collection="manual_input_data")
        )
        result = await pipeline.run(source=image_path)
    """

    def __init__(
        self,
        extractor: BaseExtractor,
        transformer: BaseTransformer,
        validator: BaseValidator,
        loader: BaseLoader,
    ):
        self.extractor = extractor
        self.transformer = transformer
        self.validator = validator
        self.loader = loader

    async def run(self, source: Any, **kwargs) -> LoadResult:
        """
        执行完整管道流程

        Args:
            source: 数据来源（路径/URL/参数等）
            **kwargs: 传递给 extractor 的额外参数

        Returns:
            LoadResult，最终加载结果
        """
        logger.info(f"🚀 Pipeline 开始: extractor={self.extractor.source_type}")

        # Step 1: Extract
        raw_records = await self.extractor.extract(source, **kwargs)
        logger.info(f"   Extract 完成: {len(raw_records)} 条原始记录")
        if not raw_records:
            logger.warning("   无原始数据，管道提前结束")
            return LoadResult()

        # Step 2: Transform
        clean_records = await self.transformer.transform(raw_records)
        logger.info(f"   Transform 完成: {len(clean_records)} 条清洗后记录")

        # Step 3: Validate
        validation_result = await self.validator.validate(clean_records)
        if validation_result.has_errors:
            error_msg = "; ".join(validation_result.errors)
            logger.error(f"   Validation 失败: {error_msg}")
            raise ValueError(f"数据校验未通过: {error_msg}")
        if validation_result.has_warnings:
            for w in validation_result.warnings:
                logger.warning(f"   Validation 警告: {w}")

        # Step 4: Load
        load_result = await self.loader.load(clean_records)
        logger.info(
            f"✅ Pipeline 完成: "
            f"inserted={load_result.inserted}, "
            f"updated={load_result.updated}, "
            f"skipped={load_result.skipped}, "
            f"errors={len(load_result.errors)}"
        )
        return load_result

    def __repr__(self) -> str:
        return (
            f"DataPipeline("
            f"extractor={self.extractor.source_type}, "
            f"loader={self.loader.target_type})"
        )
