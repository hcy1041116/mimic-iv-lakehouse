import pytest

from common.config import REPO_ROOT, load_config, table_location
from common.spark import ensure_schemas


def test_local_paths_are_relative_to_repo_root():
    cfg = load_config("local")
    assert cfg.source_root == str(REPO_ROOT / "data")
    assert cfg.lakehouse_root == str(REPO_ROOT / "output" / "lakehouse")


def test_local_table_is_delta_path():
    cfg = load_config("local")
    assert table_location(cfg, "silver.patient") == f"{cfg.lakehouse_root}/silver/patient"


def test_databricks_table_is_three_part_name():
    cfg = load_config("databricks")
    assert table_location(cfg, "silver.patient") == "mimic_demo.silver.patient"


def test_both_environments_fix_timezone_to_utc():
    assert load_config("local").session_timezone == "UTC"
    assert load_config("databricks").session_timezone == "UTC"


@pytest.mark.parametrize("name", ["patient", "silver.", "silver.patient.v2", "raw.patient"])
def test_bad_logical_name_is_rejected(name):
    with pytest.raises(ValueError):
        table_location(load_config("local"), name)


class RecordingSpark:
    """只記下收到的 SQL，用來測 Databricks 端會下哪些指令。"""

    def __init__(self):
        self.statements = []

    def sql(self, statement):
        self.statements.append(statement)


def test_ensure_schemas_creates_every_layer_on_databricks():
    spark = RecordingSpark()
    ensure_schemas(spark, load_config("databricks"))
    assert spark.statements == [
        f"CREATE SCHEMA IF NOT EXISTS mimic_demo.{layer}"
        for layer in ("bronze", "silver", "gold", "quality", "ops")
    ]


def test_ensure_schemas_does_nothing_locally():
    spark = RecordingSpark()
    ensure_schemas(spark, load_config("local"))
    assert spark.statements == []
