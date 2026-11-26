"""各環境的設定，以及邏輯表名到實際位置的對應。

程式裡只寫邏輯表名，格式是「層.表」，例如 `silver.patient`。
實際存在哪裡由 `conf/<env>.toml` 決定：
- local：`<lakehouse_root>/<層>/<表>` 的 Delta 路徑
- databricks：`<catalog>.<層>.<表>` 的 Unity Catalog 表
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONF_DIR = REPO_ROOT / "conf"
LAYERS = ("bronze", "silver", "gold", "quality", "ops")


@dataclass(frozen=True)
class Config:
    platform: str
    source_root: str
    session_timezone: str
    lakehouse_root: str | None = None
    catalog: str | None = None


def load_config(env: str, conf_dir: Path = CONF_DIR) -> Config:
    """讀 `conf/<env>.toml`。local 的相對路徑換成以 repo 根目錄為準的絕對路徑。"""
    with open(conf_dir / f"{env}.toml", "rb") as f:
        raw = tomllib.load(f)

    platform = raw["platform"]
    if platform == "local":
        return Config(
            platform=platform,
            source_root=str(REPO_ROOT / raw["source_root"]),
            session_timezone=raw["session_timezone"],
            lakehouse_root=str(REPO_ROOT / raw["lakehouse_root"]),
        )
    if platform == "databricks":
        return Config(
            platform=platform,
            source_root=raw["source_root"],
            session_timezone=raw["session_timezone"],
            catalog=raw["catalog"],
        )
    raise ValueError(f"不認得的 platform：{platform!r}")


def table_location(cfg: Config, logical_name: str) -> str:
    """把 `層.表` 換成這個環境的實際位置：local 是路徑，databricks 是三層表名。"""
    layer, sep, table = logical_name.partition(".")
    if not sep or not table or "." in table:
        raise ValueError(f"邏輯表名要寫成「層.表」：{logical_name!r}")
    if layer not in LAYERS:
        raise ValueError(f"不認得的層 {layer!r}，只能是 {LAYERS}")

    if cfg.platform == "local":
        return f"{cfg.lakehouse_root}/{layer}/{table}"
    return f"{cfg.catalog}.{layer}.{table}"
