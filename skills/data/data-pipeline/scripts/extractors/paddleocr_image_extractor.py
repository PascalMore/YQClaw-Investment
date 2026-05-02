"""
PaddleOCR Image-to-Excel Extractor.

Wraps the paddleocr_table2excel skill (skills/common/paddleocr_table2excel/)
to convert images into Excel files, then returns the Excel as a pandas DataFrame
readable by PaddleOCRExcelTransformer.

Step 2 of the Image Portfolio Data Pipeline.
"""
import subprocess
import sys
import shutil
from pathlib import Path

import pandas as pd

from .base import BaseExtractor


class PaddleOCRImageExtractor(BaseExtractor):
    """
    Extracts structured DataFrame from portfolio table images using PaddleOCR.

    Calls the paddleocr_table2excel skill:
        .venv/bin/python scripts/table_ocr.py -i <image_path> -o <output_path>

    Then reads the output Excel and returns it as a DataFrame-wrapped dict.

    Output records format (for Transformer):
        [{"df": pd.DataFrame, "source_path": str}]
    """

    def __init__(
        self,
        skill_dir: str = None,
        output_dir: str = None,
    ):
        """
        Args:
            skill_dir: Override path to paddleocr_table2excel skill directory.
            output_dir: Directory to save intermediate Excel files.
        """
        if skill_dir is None:
            # From scripts/extractors/paddleocr_image_extractor.py:
            #   parent[1]=extractors, [2]=scripts, [3]=data-pipeline, [4]=skills
            #   -> go to workspace-yquant then common/paddleocr_table2excel
            skill_dir = (
                Path(__file__).resolve().parents[4]
                / "common"
                / "paddleocr_table2excel"
            )
        self.skill_dir = Path(skill_dir)
        self.venv_python = self.skill_dir / ".venv" / "bin" / "python"
        self.script = self.skill_dir / "scripts" / "table_ocr.py"

        if output_dir is None:
            # Default: save Excel next to the source images
            # from skills/data/data-pipeline/scripts/extractors/paddleocr_image_extractor.py
            # parents[3] = skills/, parents[4] = workspace-yquant/
            # images are at: skills/data/source/smart-money/YYYY-MM-DD/
            output_dir = (
                Path(__file__).resolve().parents[3]
                / "source"
                / "smart-money"
            )
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not self.venv_python.exists():
            raise FileNotFoundError(f"Venv python not found: {self.venv_python}")
        if not self.script.exists():
            raise FileNotFoundError(f"Script not found: {self.script}")

    @property
    def source_type(self) -> str:
        return "image_paddleocr"

    async def extract(self, source: str | list[str], **kwargs) -> list[dict]:
        """
        Run PaddleOCR on one or more images.

        Args:
            source: Single image path (str) or list of image paths.

        Returns:
            List of dicts, each containing:
                - "df": DataFrame from the generated Excel
                - "source_path": original image path
        """
        images = [source] if isinstance(source, str) else source
        results = []

        for img_path in images:
            img_path = Path(img_path)
            if not img_path.exists():
                raise FileNotFoundError(f"Image not found: {img_path}")

            # Determine output Excel path — save alongside the image in its date directory
            excel_path = img_path.with_suffix(".xlsx")

            # Run PaddleOCR pipeline
            cmd = [
                str(self.venv_python),
                str(self.script),
                "-i", str(img_path),
                "-o", str(excel_path),
            ]

            # Run in workspace root so relative image paths resolve correctly
            loop = __import__("asyncio").get_event_loop()
            proc = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(Path(__file__).resolve().parents[5]),
                ),
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"PaddleOCR failed for {img_path.name}:\n{proc.stderr}"
                )

            # Read Excel into DataFrame
            df = pd.read_excel(excel_path)

            results.append({
                "df": df,
                "source_path": str(img_path),
            })

        return results

    async def validate_source(self, source: str | list[str]) -> bool:
        """Check that all image files exist."""
        images = [source] if isinstance(source, str) else source
        return all(Path(p).exists() for p in images)
