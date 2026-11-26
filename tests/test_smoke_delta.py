"""冒煙測試：本機的 Spark + Delta 能動，時間型別寫進去讀出來不會變。"""

from datetime import datetime

from pyspark.sql import functions as F
from pyspark.sql.types import TimestampNTZType

from common.spark import read_table, write_table


def test_session_timezone_is_utc(spark):
    assert spark.conf.get("spark.sql.session.timeZone") == "UTC"


def test_timestamp_ntz_round_trip_through_delta(spark, cfg):
    source = spark.createDataFrame([("10023239", "2140-10-22 22:04:00")], "subject_id string, admittime string")
    df = source.withColumn("admittime", F.col("admittime").cast("timestamp_ntz"))

    write_table(df, cfg, "ops.smoke_test")
    back = read_table(spark, cfg, "ops.smoke_test")

    assert back.schema["admittime"].dataType == TimestampNTZType()
    assert back.collect()[0]["admittime"] == datetime(2140, 10, 22, 22, 4)
