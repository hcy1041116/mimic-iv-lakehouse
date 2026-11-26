import pytest

from common.config import REPO_ROOT, load_config, table_location


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
