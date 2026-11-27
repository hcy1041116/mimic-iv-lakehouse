from dataclasses import replace
from pathlib import Path

import pytest

from common.config import load_config
from common.spark import get_spark
from ingest.bronze import SOURCE_FILES


@pytest.fixture(scope="session")
def cfg(tmp_path_factory):
    """本機 config，但表寫到暫存資料夾，測試不會動到 output/。"""
    lakehouse_root = tmp_path_factory.mktemp("lakehouse")
    return replace(load_config("local"), lakehouse_root=str(lakehouse_root))


@pytest.fixture(scope="session")
def spark(cfg):
    session = get_spark(cfg)
    yield session
    session.stop()


@pytest.fixture(scope="module")
def real_cfg(cfg, tmp_path_factory):
    """讀真實展示版資料的 config。資料不進 Git，沒下載時跳過；每個測試檔有自己的 lakehouse。"""
    if not all((Path(cfg.source_root) / rel).exists() for rel in SOURCE_FILES.values()):
        pytest.skip("沒有下載 MIMIC-IV 展示版資料")
    return replace(cfg, lakehouse_root=str(tmp_path_factory.mktemp("real")))
