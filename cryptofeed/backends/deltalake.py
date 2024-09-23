"""
Copyright (C) 2017-2024 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
"""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from deltalake import DeltaTable, write_deltalake

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue
from cryptofeed.defines import (BALANCES, CANDLES, FILLS, FUNDING, LIQUIDATIONS,
                                OPEN_INTEREST, ORDER_INFO, TICKER, TRADES, TRANSACTIONS)


# Add these lines after the imports
# logging.basicConfig(level=logging.DEBUG)
# logging.getLogger().setLevel(logging.DEBUG)

LOG = logging.getLogger("feedhandler")


class DeltaLakeCallback(BackendQueue):
    def __init__(
        self,
        base_path: str,
        key: Optional[str] = None,
        custom_columns: Optional[Dict[str, str]] = None,
        partition_cols: Optional[List[str]] = None,
        optimize_interval: int = 1000,
        z_order_cols: Optional[List[str]] = None,
        time_travel: bool = True,
        storage_options: Optional[Dict[str, Any]] = None,
        numeric_type: Union[type, str] = float,
        none_to: Any = None,
        batch_size: int = 10000,
        flush_interval: float = 10.0,
        custom_transformations: Optional[List[callable]] = None,
        **kwargs: Any,
    ):
        LOG.debug("Initializing DeltaLakeCallback")
        super().__init__()
        self.key = key or self.default_key
        self.base_path = base_path
        self.delta_table_path = f"{self.base_path}/{self.key}"
        self.custom_columns = custom_columns or {}
        self.partition_cols = partition_cols or ["exchange", "symbol", "dt"]
        self.optimize_interval = optimize_interval
        self.z_order_cols = z_order_cols or self._default_z_order_cols()
        self.time_travel = time_travel or False
        self.storage_options = storage_options or {}
        self.write_count = 0
        self.running = True
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.transformations = [
            self._rename_custom_columns,
            self._convert_datetime_columns,
            self._convert_int_columns,
            self._ensure_partition_columns,
            self._handle_missing_values,
        ]
        if custom_transformations:
            self.transformations.extend(custom_transformations)
        # Validate configuration parameters
        self._validate_configuration()
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.batch = []
        self.last_flush_time = time.time()

    def _validate_configuration(self):
        if self.optimize_interval <= 0:
            raise ValueError("optimize_interval must be a positive integer")

        if not isinstance(self.partition_cols, list) or not all(
            isinstance(col, str) for col in self.partition_cols
        ):
            raise TypeError("partition_cols must be a list of strings")

        if not isinstance(self.z_order_cols, list) or not all(
            isinstance(col, str) for col in self.z_order_cols
        ):
            raise TypeError("z_order_cols must be a list of strings")

        if not isinstance(self.storage_options, dict):
            raise TypeError("storage_options must be a dictionary")

        if not isinstance(self.numeric_type, (type, str)):
            raise TypeError("numeric_type must be a type or a string")

    def _default_z_order_cols(self) -> List[str]:
        common_cols = ["timestamp"]
        data_specific_cols = {
            TRADES: ["price", "amount"],
            FUNDING: ["rate"],
            TICKER: ["bid", "ask"],
            OPEN_INTEREST: ["open_interest"],
            LIQUIDATIONS: ["quantity", "price"],
            "book": [],  # Book data is typically queried by timestamp and symbol
            CANDLES: ["open", "close", "high", "low"],
            ORDER_INFO: ["status", "price", "amount"],
            TRANSACTIONS: ["type", "amount"],
            BALANCES: ["balance"],
            FILLS: ["price", "amount"],
        }
        z_order_cols = common_cols + data_specific_cols.get(self.key, [])
        # Remove any columns that are already in partition_cols
        return [col for col in z_order_cols if col not in self.partition_cols]

    async def writer(self):
        LOG.debug("Writer method started")
        while self.running:
            try:
                async with self.read_queue() as updates:
                    LOG.debug(f"Read queue returned: {updates}")
                    if updates:
                        LOG.debug(f"Received {len(updates)} updates for processing.")
                        self.batch.extend(updates)

                        if len(self.batch) >= self.batch_size or (time.time() - self.last_flush_time) >= self.flush_interval:
                            await self._process_batch()
                    else:
                        # Check if we need to flush based on time
                        if (time.time() - self.last_flush_time) >= self.flush_interval and self.batch:
                            await self._process_batch()
                        else:
                            LOG.debug("No updates received, continuing loop")
                            await asyncio.sleep(1)  # Add a small delay to prevent busy-waiting
            except Exception as e:
                LOG.error(f"Error in writer method: {e}", exc_info=True)
        LOG.debug("Writer method ended")

    async def _process_batch(self):
        df = pd.DataFrame(self.batch)
        self._transform_columns(df)
        self._validate_columns(df)
        await self._write_batch(df)

        self.batch = []
        self.last_flush_time = time.time()

    def _validate_columns(self, df: pd.DataFrame):
        LOG.debug("Validating DataFrame columns.")
        # Check for required columns
        required_columns = ["exchange", "symbol", "dt"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

        # Validate partition columns
        for col in self.partition_cols:
            if col not in df.columns:
                raise ValueError(f"Partition column '{col}' not found in DataFrame")
            if df[col].isnull().any():
                raise ValueError(f"Partition column '{col}' contains null values")

        # Validate data types
        expected_types = {
            "exchange": "object",
            "symbol": "object",
            "dt": "object",
            "timestamp": "datetime64[us]",
            "receipt_timestamp": "datetime64[us]",
        }
        for col, expected_type in expected_types.items():
            if expected_type == "datetime64[us]":
                # Ensure datetime columns are in microsecond precision
                df[col] = df[col].astype("datetime64[us]")
            if col in df.columns:
                if not df[col].dtype == expected_type:
                    raise TypeError(
                        f"Column '{col}' should be of type {expected_type}, but is {df[col].dtype}"
                    )

        LOG.debug("DataFrame columns validation completed successfully.")

    def _transform_columns(self, df: pd.DataFrame):
        LOG.debug("Transforming columns in DataFrame.")
        for transformation in self.transformations:
            transformation(df)

    def _rename_custom_columns(self, df: pd.DataFrame):
        if self.custom_columns:
            LOG.debug("Renaming columns based on custom_columns configuration.")
            df.rename(columns=self.custom_columns, inplace=True)

    def _reorder_columns(self, df: pd.DataFrame):
        LOG.debug("Reordering columns to prioritize exchange and symbol.")
        priority_cols = ["exchange", "symbol"]
        other_cols = [col for col in df.columns if col not in priority_cols]
        df = df[priority_cols + other_cols]

    def _convert_datetime_columns(self, df: pd.DataFrame):
        LOG.debug("Converting datetime columns to UTC and microsecond precision.")
        INVALID_DATE = pd.Timestamp('1900-01-01').date()

        for col in ['timestamp', 'receipt_timestamp']:
            if col in df.columns:
                # Convert timestamp (seconds since epoch) to UTC datetime
                df[col] = pd.to_datetime(df[col], unit='s', utc=True).dt.tz_localize(None)
                LOG.debug(f"Sample {col} after conversion: {df[col].iloc[0] if len(df) > 0 else 'N/A'}")

        # Create 'dt' column, prioritizing 'timestamp', then 'receipt_timestamp', fallback to INVALID_DATE
        if "timestamp" in df.columns:
            df["dt"] = df["timestamp"].dt.date
        elif "receipt_timestamp" in df.columns:
            df["dt"] = df["receipt_timestamp"].dt.date
        else:
            LOG.warning("Neither timestamp nor receipt_timestamp column found. Using invalid date for 'dt'.")
            df["dt"] = INVALID_DATE

        # Log sample of 'dt' column
        if "dt" in df.columns and len(df) > 0:
            LOG.debug(f"Sample 'dt' value: {df['dt'].iloc[0]}")

        LOG.debug("Datetime columns converted and 'dt' column created.")

    def _convert_int_columns(self, df: pd.DataFrame):
        LOG.debug("Converting integer columns.")
        int_columns = ["id", "trade_id", "trades"]
        for col in int_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype(
                    "Int64"
                )  # Use nullable integer type

    def _ensure_partition_columns(self, df: pd.DataFrame):
        LOG.debug("Ensuring all partition columns are present and not null.")
        for col in self.partition_cols:
            if col not in df.columns:
                if col in ["exchange", "symbol"]:
                    df[col] = "unknown"
                elif col == "dt":
                    # 'dt' should already be created in _convert_datetime_columns
                    LOG.warning("'dt' column not found. This should not happen.")
                    df[col] = pd.Timestamp.now().date()
                else:
                    df[col] = "unknown"

            # Fill any remaining null values
            if df[col].isnull().any():
                LOG.warning(
                    f"Found null values in partition column {col}. Filling with default values."
                )
                df[col] = df[col].fillna(
                    "unknown"
                    if col != "dt"
                    else pd.Timestamp.now().date()
                )

    def _handle_missing_values(self, df: pd.DataFrame):
        LOG.debug("Handling missing values.")
        for col in df.columns:
            if col in ["exchange", "symbol"]:  # Removed 'dt' from this list
                # These are partition columns and should never be null
                if df[col].isnull().any():
                    LOG.warning(
                        f"Found null values in partition column {col}. Filling with default values."
                    )
                    df[col] = df[col].fillna("unknown")
            elif pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(
                    self.none_to if self.none_to is not None else 0
                )
            elif pd.api.types.is_string_dtype(df[col]):
                df[col] = df[col].fillna(
                    self.none_to if self.none_to is not None else ""
                )
            elif pd.api.types.is_bool_dtype(df[col]):
                df[col] = df[col].fillna(
                    self.none_to if self.none_to is not None else False
                )
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].fillna(
                    self.none_to if self.none_to is not None else pd.NaT
                )
            else:
                df[col] = df[col].fillna(
                    self.none_to if self.none_to is not None else ""
                )

    async def _write_batch(self, df: pd.DataFrame):
        if df.empty:
            LOG.warning("DataFrame is empty. Skipping write operation.")
            return

        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                LOG.debug(
                    f"Attempting to write batch to Delta Lake (Attempt {attempt + 1}/{max_retries})."
                )

                # Logging statements just before write_deltalake
                # sample_size = min(5, len(df))  # Show up to 5 rows
                # LOG.debug(f"Sample of DataFrame to be written (first {sample_size} rows):")
                # LOG.debug(df.head(sample_size).to_string())
                LOG.debug("DataFrame dtypes:")
                LOG.debug(df.dtypes.to_string())
                LOG.warning(f"Writing batch of {len(df)} records to {self.delta_table_path}")

                write_deltalake(
                    self.delta_table_path,
                    df,
                    mode="append",
                    partition_by=self.partition_cols,
                    schema_mode="merge",
                    storage_options=self.storage_options,
                )
                self.write_count += 1

                if self.write_count % self.optimize_interval == 0:
                    await self._optimize_table()

                if self.time_travel:
                    self._update_metadata()

                LOG.warning("Batch write successful.")
                break  # Exit the retry loop if write is successful

            except Exception as e:
                LOG.error(f"Error writing to Delta Lake on attempt {attempt + 1}/{max_retries}: {e}")
                LOG.error(f"DataFrame schema:\n{df.dtypes}")
                LOG.error(f"DataFrame:\n{df}")

                if attempt < max_retries - 1:
                    LOG.warning(f"Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    LOG.error(
                        "Max retries reached. Failed to write batch to Delta Lake."
                    )

    async def _optimize_table(self):
        LOG.debug(
            f"Running OPTIMIZE on table {self.delta_table_path}"
        )
        dt = DeltaTable(self.delta_table_path, storage_options=self.storage_options)
        dt.optimize.compact()
        if self.z_order_cols:
            dt.optimize.z_order(self.z_order_cols)
        LOG.debug("OPTIMIZE operation completed.")

    def _update_metadata(self):
        dt = DeltaTable(self.delta_table_path, storage_options=self.storage_options)
        LOG.info(f"Updating metadata for time travel. Current version: {dt.version()}")

    async def stop(self):
        LOG.info("Stopping DeltaLakeCallback writer.")
        self.running = False
        # Flush any remaining data
        if self.batch:
            await self._process_batch()

    def get_version(self, timestamp: Optional[int] = None) -> Optional[int]:
        if self.time_travel:
            dt = DeltaTable(self.delta_table_path, storage_options=self.storage_options)
            if timestamp:
                version = dt.version_at_timestamp(timestamp)
                LOG.info(f"Retrieved version {version} for timestamp {timestamp}.")
                return version
            else:
                version = dt.version()
                LOG.info(f"Retrieved current version {version}.")
                return version
        else:
            LOG.warning("Time travel is not enabled for this table")
            return None


class TradeDeltaLake(DeltaLakeCallback, BackendCallback):
    default_key = TRADES
    """
    Schema:
    - timestamp: datetime64[us] (from 'date' column)
    - receipt_timestamp: datetime64[us]
    - dt: date
    - exchange: category
    - symbol: category
    - id: int64 (nullable)
    - side: category
    - amount: float64
    - price: float64
    - type: category (nullable)
    - trade_id: int64
    """


class FundingDeltaLake(DeltaLakeCallback, BackendCallback):
    default_key = FUNDING
    """
    Schema:
    - timestamp: datetime64[us] (from 'date' column)
    - receipt_timestamp: datetime64[us]
    - dt: date
    - exchange: category
    - symbol: category
    - mark_price: float64 (nullable)
    - rate: float64
    - next_funding_time: datetime64[us] (nullable)
    - predicted_rate: float64 (nullable)
    """


class TickerDeltaLake(DeltaLakeCallback, BackendCallback):
    default_key = TICKER
    """
    Schema:
    - timestamp: datetime64[us] (from 'date' column)
    - receipt_timestamp: datetime64[us]
    - dt: date
    - exchange: category
    - symbol: category
    - bid: float64
    - ask: float64
    """


class OpenInterestDeltaLake(DeltaLakeCallback, BackendCallback):
    default_key = OPEN_INTEREST
    """
    Schema:
    - timestamp: datetime64[us] (from 'date' column)
    - receipt_timestamp: datetime64[us]
    - dt: date
    - exchange: category
    - symbol: category
    - open_interest: float64
    """


class LiquidationsDeltaLake(DeltaLakeCallback, BackendCallback):
    default_key = LIQUIDATIONS
    """
    Schema:
    - timestamp: datetime64[us] (from 'date' column)
    - receipt_timestamp: datetime64[us]
    - dt: date
    - exchange: category
    - symbol: category
    - side: category
    - quantity: float64
    - price: float64
    - id: int64
    - status: category
    """


class BookDeltaLake(DeltaLakeCallback, BackendBookCallback):
    default_key = "book"
    """
    Schema:
    - timestamp: datetime64[us] (from 'date' column)
    - receipt_timestamp: datetime64[us]
    - dt: date
    - exchange: category
    - symbol: category
    - delta: dict (nullable, contains 'bid' and 'ask' updates)
    - book: dict (contains full order book snapshot when available)
    """

    def __init__(self, *args, snapshots_only=False, snapshot_interval=1000, **kwargs):
        self.snapshots_only = snapshots_only
        self.snapshot_interval = snapshot_interval
        self.snapshot_count = defaultdict(int)
        super().__init__(*args, **kwargs)


class CandlesDeltaLake(DeltaLakeCallback, BackendCallback):
    default_key = CANDLES
    """
    Schema:
    - timestamp: datetime64[us] (from 'date' column)
    - receipt_timestamp: datetime64[us]
    - dt: date
    - exchange: category
    - symbol: category
    - start: datetime64[us]
    - stop: datetime64[us]
    - interval: string
    - trades: int64 (nullable)
    - open: float64
    - close: float64
    - high: float64
    - low: float64
    - volume: float64
    - closed: bool (nullable)
    """


class OrderInfoDeltaLake(DeltaLakeCallback, BackendCallback):
    default_key = ORDER_INFO
    """
    Schema:
    - timestamp: datetime64[us] (from 'date' column)
    - receipt_timestamp: datetime64[us]
    - dt: date
    - exchange: category
    - symbol: category
    - id: int64
    - client_order_id: string (nullable)
    - side: category
    - status: category
    - type: category
    - price: float64
    - amount: float64
    - remaining: float64 (nullable)
    - account: string (nullable)
    """


class TransactionsDeltaLake(DeltaLakeCallback, BackendCallback):
    default_key = TRANSACTIONS
    """
    Schema:
    - timestamp: datetime64[us] (from 'date' column)
    - receipt_timestamp: datetime64[us]
    - dt: date
    - exchange: category
    - currency: category
    - type: category
    - status: category
    - amount: float64
    """


class BalancesDeltaLake(DeltaLakeCallback, BackendCallback):
    default_key = BALANCES
    """
    Schema:
    - timestamp: datetime64[us] (from 'date' column)
    - receipt_timestamp: datetime64[us]
    - dt: date
    - exchange: category
    - currency: category
    - balance: float64
    - reserved: float64 (nullable)
    """


class FillsDeltaLake(DeltaLakeCallback, BackendCallback):
    default_key = FILLS
    """
    Schema:
    - timestamp: datetime64[us] (from 'date' column)
    - receipt_timestamp: datetime64[us]
    - dt: date
    - exchange: category
    - symbol: category
    - price: float64
    - amount: float64
    - side: category
    - fee: float64 (nullable)
    - id: int64
    - order_id: int64
    - liquidity: category
    - type: category
    - account: string (nullable)
    """
