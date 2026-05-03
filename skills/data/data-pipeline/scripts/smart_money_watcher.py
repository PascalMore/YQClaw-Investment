"""
Smart Money File Watcher
=========================
监控 data/source/smart-money/{date}/image 和 message 目录，
新文件出现时自动触发对应 Pipeline（OCR 或 Text）。

Usage:
    python smart_money_watcher.py                    # 前台运行
    python smart_money_watcher.py --daemon           # 后台运行
    python smart_money_watcher.py --once 2026-05-03  # 单次扫描指定日期
"""
import argparse
import asyncio
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# 第三方库
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

# 本地模块
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_message_pipeline import run_pipeline as run_message_pipeline_async, parse_text_to_df, save_excel
from extractors.paddleocr_image_extractor import PaddleOCRImageExtractor
from transformers.paddleocr_excel_transformer import PaddleOCRExcelTransformer
from transformers.image_portfolio_normalizer import normalize_all
from validators.portfolio_validator import validate_basic_info, validate_nav, validate_position, ValidationResult
from loaders.mongodb_loader import PortfolioMongoLoader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 路径配置
WORKSPACE = Path(__file__).resolve().parents[4]  # workspace-yquant
SMART_MONEY_ROOT = WORKSPACE / "skills" / "data" / "source" / "smart-money"
SOURCE_ROOT = WORKSPACE / "skills" / "data" / "source" / "smart-money"


class PortfolioPipeline:
    """封装 Image 和 Message 两种 Pipeline 的统一入口"""

    @staticmethod
    def get_date_dir(date_str: Optional[str] = None) -> Path:
        """获取或创建指定日期的目录"""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        date_dir = SOURCE_ROOT / date_str
        date_dir.mkdir(parents=True, exist_ok=True)
        return date_dir

    @staticmethod
    def ensure_subdirs(date_str: str) -> tuple[Path, Path]:
        """确保日期目录下有 image 和 message 子目录"""
        date_dir = PortfolioPipeline.get_date_dir(date_str)
        image_dir = date_dir / "image"
        message_dir = date_dir / "message"
        image_dir.mkdir(parents=True, exist_ok=True)
        message_dir.mkdir(parents=True, exist_ok=True)
        return image_dir, message_dir

    @staticmethod
    async def process_image(image_path: Path, date_str: Optional[str] = None) -> dict:
        """
        处理图片持仓数据：OCR → Excel → Normalize → Validate → MongoDB
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        # 确保目录存在（收到数据时才创建）
        image_dir, message_dir = PortfolioPipeline.ensure_subdirs(date_str)

        # 生成带秒级精度的新文件名（避免同一分钟内重名）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"portfolio_{timestamp}"
        new_image_path = image_dir / f"{base_name}{image_path.suffix}"
        
        # 重命名原始图片
        import shutil
        shutil.move(str(image_path), str(new_image_path))
        image_path = new_image_path

        logger.info(f"[Image Pipeline] 开始处理: {image_path}")

        try:
            # Step 1: OCR Image → Excel (与图片同名，仅扩展名不同)
            extractor = PaddleOCRImageExtractor()
            records = await extractor.extract(str(image_path))

            if not records:
                raise ValueError("OCR 未提取到数据")

            df = records[0]["df"]
            excel_path = image_path.with_suffix(".xlsx")

            logger.info(f"[Image Pipeline] OCR 完成: {excel_path} ({len(df)} rows)")

            # Step 2: Transform
            transformer = PaddleOCRExcelTransformer()
            nested = transformer.transform(records)
            normalized = normalize_all(nested[0])

            logger.info(f"[Image Pipeline] Normalized: basic={len(normalized['basic_info'])}, "
                        f"nav={len(normalized['nav'])}, pos={len(normalized['position'])}")

            # Step 3: Validate
            vr_basic = validate_basic_info(normalized["basic_info"])
            vr_nav = validate_nav(normalized["nav"])
            vr_pos = validate_position(normalized["position"])
            merged = ValidationResult()
            merged.merge(vr_basic)
            merged.merge(vr_nav)
            merged.merge(vr_pos)

            if merged.has_errors:
                logger.error(f"[Image Pipeline] Validation errors: {merged.errors}")
                raise ValueError(f"Validation failed: {'; '.join(merged.errors)}")

            # Step 4: MongoDB
            loader = PortfolioMongoLoader()
            result = loader.load_all(normalized)

            mongodb_result = {"inserted": result.get("inserted", 0), "updated": result.get("updated", 0), "skipped": result.get("skipped", 0)}
            logger.info(f"[Image Pipeline] ✅ 完成: inserted={mongodb_result['inserted']}, "
                        f"updated={mongodb_result['updated']}, skipped={mongodb_result['skipped']}")

            return {
                "type": "image",
                "source": str(image_path),
                "excel": str(excel_path),
                "rows": len(df),
                "mongodb": mongodb_result,
                "validation": {"valid": merged.valid, "errors": merged.errors, "warnings": merged.warnings},
            }

        except Exception as e:
            logger.error(f"[Image Pipeline] ❌ 失败: {e}")
            raise

    @staticmethod
    async def process_message(message_path: Path, date_str: Optional[str] = None) -> dict:
        """
        处理文本持仓数据：Parse → Excel → Normalize → Validate → MongoDB
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        # 确保目录存在（收到数据时才创建）
        image_dir, message_dir = PortfolioPipeline.ensure_subdirs(date_str)

        # 生成带秒级精度的新文件名（避免同一分钟内重名）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"portfolio_{timestamp}"
        new_message_path = message_dir / f"{base_name}{message_path.suffix}"
        
        # 重命名原始 message 文件
        import shutil
        shutil.move(str(message_path), str(new_message_path))
        message_path = new_message_path

        logger.info(f"[Message Pipeline] 开始处理: {message_path}")

        try:
            # Step 1: 读取文本并解析
            raw_text = message_path.read_text(encoding="utf-8")
            df = parse_text_to_df(raw_text)

            if df.empty:
                raise ValueError("解析后无有效数据")

            # Step 2: 保存 Excel（与原始 message 文件同名，仅扩展名不同）
            excel_path = save_excel(df, date_str, SOURCE_ROOT, input_filename=str(message_path))
            logger.info(f"[Message Pipeline] Excel → {excel_path} ({len(df)} rows)")

            # Step 3: Transform
            transformer = PaddleOCRExcelTransformer()
            records = [{"df": df}]
            nested = transformer.transform(records)
            normalized = normalize_all(nested[0])

            logger.info(f"[Message Pipeline] Normalized: basic={len(normalized['basic_info'])}, "
                        f"nav={len(normalized['nav'])}, pos={len(normalized['position'])}")

            # Step 4: Validate
            vr_basic = validate_basic_info(normalized["basic_info"])
            vr_nav = validate_nav(normalized["nav"])
            vr_pos = validate_position(normalized["position"])
            merged = ValidationResult()
            merged.merge(vr_basic)
            merged.merge(vr_nav)
            merged.merge(vr_pos)

            if merged.has_errors:
                logger.error(f"[Message Pipeline] Validation errors: {merged.errors}")
                raise ValueError(f"Validation failed: {'; '.join(merged.errors)}")

            # Step 5: MongoDB
            loader = PortfolioMongoLoader()
            result = loader.load_all(normalized)

            mongodb_result = {"inserted": result.get("inserted", 0), "updated": result.get("updated", 0), "skipped": result.get("skipped", 0)}
            logger.info(f"[Message Pipeline] ✅ 完成: inserted={mongodb_result['inserted']}, "
                        f"updated={mongodb_result['updated']}, skipped={mongodb_result['skipped']}")

            return {
                "type": "message",
                "source": str(message_path),
                "excel": str(excel_path),
                "rows": len(df),
                "mongodb": mongodb_result,
                "validation": {"valid": merged.valid, "errors": merged.errors, "warnings": merged.warnings},
            }

        except Exception as e:
            logger.error(f"[Message Pipeline] ❌ 失败: {e}")
            raise

    @staticmethod
    def detect_date_from_path(path: Path) -> str:
        """从路径中提取日期，如 data/source/smart-money/2026-05-03/image/file.png"""
        parts = path.parts
        for part in parts:
            if len(part) == 10 and part[4] == "-" and part[7] == "-":
                return part  # YYYY-MM-DD
        return datetime.now().strftime("%Y-%m-%d")


class SmartMoneyHandler(FileSystemEventHandler):
    """文件系统事件处理器"""

    def __init__(self, pipeline: PortfolioPipeline, processed_files: set):
        super().__init__()
        self.pipeline = pipeline
        self.processed_files = processed_files
        # 限制并发，避免同一文件被多次处理
        self._processing = set()

    def _is_our_directory(self, path: str) -> bool:
        """检查路径是否在我们的监控范围内"""
        path_obj = Path(path)
        # 只处理 image 或 message 子目录
        if path_obj.parent.name not in ("image", "message"):
            return False
        # 确保日期目录格式正确
        date_str = self.pipeline.detect_date_from_path(path_obj)
        return date_str is not None

    def _get_file_type(self, path: Path) -> Optional[str]:
        """根据路径判断文件类型"""
        parent_name = path.parent.name
        suffix = path.suffix.lower()

        if parent_name == "image" and suffix in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
            return "image"
        elif parent_name == "message" and suffix in (".txt", ".csv", ".tsv", ".md"):
            return "message"
        return None

    def on_created(self, event: FileCreatedEvent):
        """新文件创建时触发"""
        if event.is_directory:
            return

        path = Path(event.src_path)
        file_type = self._get_file_type(path)

        if file_type is None:
            return

        # 避免重复处理
        if str(path) in self._processing:
            return

        # 等待文件写入完成（简单策略：等待1秒）
        time.sleep(1)

        # 检查文件是否已处理过
        if str(path) in self.processed_files:
            logger.info(f"文件已处理过，跳过: {path}")
            return

        self._processing.add(str(path))
        try:
            date_str = self.pipeline.detect_date_from_path(path)
            logger.info(f"检测到新文件: {path} (type={file_type}, date={date_str})")

            loop = asyncio.get_event_loop()
            if file_type == "image":
                result = loop.run_until_complete(self.pipeline.process_image(path, date_str))
            else:
                result = loop.run_until_complete(self.pipeline.process_message(path, date_str))

            self.processed_files.add(str(path))
            logger.info(f"处理结果: {result}")

        except Exception as e:
            logger.error(f"处理文件失败 {path}: {e}")
        finally:
            self._processing.discard(str(path))


def scan_existing_files(date_str: Optional[str] = None) -> list[Path]:
    """扫描已存在的文件（用于 --once 模式）"""
    files = []
    if date_str:
        dates = [date_str]
    else:
        # 扫描所有日期目录
        dates = [d.name for d in SOURCE_ROOT.iterdir() if d.is_dir() and len(d.name) == 10]

    for d in dates:
        for subdir in ["image", "message"]:
            subdir_path = SOURCE_ROOT / d / subdir
            if subdir_path.exists():
                for f in subdir_path.iterdir():
                    if f.is_file():
                        files.append(f)
    return files


async def process_existing_files(processed_files: set) -> list[dict]:
    """处理已存在的文件（不重复处理）"""
    pipeline = PortfolioPipeline()
    results = []

    for path in scan_existing_files():
        if str(path) in processed_files:
            continue

        file_type = SmartMoneyHandler._get_file_type(None, path) if False else None
        # 简单判断
        if "image" in str(path):
            file_type = "image"
        elif "message" in str(path):
            file_type = "message"
        else:
            continue

        try:
            if file_type == "image":
                result = await pipeline.process_image(path)
            else:
                result = await pipeline.process_message(path)

            processed_files.add(str(path))
            results.append(result)
        except Exception as e:
            logger.error(f"处理失败 {path}: {e}")

    return results


def run_watcher(processed_files: set, daemon: bool = False):
    """运行文件监控"""
    pipeline = PortfolioPipeline()

    today = datetime.now().strftime("%Y-%m-%d")
    handler = SmartMoneyHandler(pipeline, processed_files)
    observer = Observer()

    # 只监控已存在的日期目录，不预先创建
    for date_dir in SOURCE_ROOT.iterdir():
        if date_dir.is_dir() and len(date_dir.name) == 10:
            for subdir in ["image", "message"]:
                subdir_path = date_dir / subdir
                if subdir_path.exists():
                    observer.schedule(handler, str(subdir_path), recursive=False)
                    logger.info(f"监控: {subdir_path}")

    # 监控根目录，以便检测到新日期目录时自动添加监控
    observer.schedule(handler, str(SOURCE_ROOT), recursive=False)
    logger.info(f"监控根目录: {SOURCE_ROOT}")
    logger.info("提示: 目录将在收到第一条数据时自动创建")

    observer.start()
    logger.info("=" * 50)
    logger.info("Smart Money Watcher 已启动")
    logger.info(f"监控目录: {SOURCE_ROOT}")
    logger.info(f"处理过的文件: {len(processed_files)}")
    logger.info("按 Ctrl+C 停止")
    logger.info("=" * 50)

    try:
        while True:
            time.sleep(10)
            # 定期检查新日期目录
            for d in SOURCE_ROOT.iterdir():
                if d.is_dir() and len(d.name) == 10 and d.name not in [handler.detect_date_from_path(Path(p)) for p in processed_files]:
                    for subdir in ["image", "message"]:
                        subdir_path = d / subdir
                        if subdir_path.exists():
                            observer.schedule(handler, str(subdir_path.parent), recursive=False)
                            logger.info(f"新增监控: {subdir_path.parent}")
    except KeyboardInterrupt:
        logger.info("停止监控...")
        observer.stop()
    observer.join()


def main():
    parser = argparse.ArgumentParser(description="Smart Money File Watcher")
    parser.add_argument("--daemon", action="store_true", help="后台运行")
    parser.add_argument("--once", metavar="DATE", help="单次扫描指定日期，如 2026-05-03")
    parser.add_argument("--scan-all", action="store_true", help="扫描所有已存在的文件")
    args = parser.parse_args()

    # 加载已处理文件记录
    processed_file = WORKSPACE / ".smart_money_processed.txt"
    processed_files = set()
    if processed_file.exists():
        processed_files = set(processed_file.read_text().splitlines())

    def save_processed():
        processed_file.write_text("\n".join(processed_files))

    if args.once:
        # 单次扫描模式
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(process_existing_files(processed_files))
        for r in results:
            print(f"✅ {r}")
        save_processed()
        return

    if args.scan_all:
        loop = asyncio.get_event_loop()
        results = loop.run_until_complete(process_existing_files(processed_files))
        for r in results:
            print(f"✅ {r}")
        save_processed()
        print(f"\n已处理 {len(results)} 个文件")
        return

    # 守护进程模式
    run_watcher(processed_files, daemon=args.daemon)


if __name__ == "__main__":
    main()
