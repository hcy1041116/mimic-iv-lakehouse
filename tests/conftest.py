from dataclasses import replace

import pytest

from common.config import load_config
from common.spark import get_spark


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
