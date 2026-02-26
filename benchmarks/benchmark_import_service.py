"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: benchmark_import_service.py
@DateTime: 2026-02-26
@Docs: ImportExportService performance benchmark scaffold.
ImportExportService 性能基准脚手架。
"""

import argparse
import asyncio
import csv
import io
import json
import math
import random
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from starlette.datastructures import Headers

from fastapi_import_export.config import ImportExportConfig
from fastapi_import_export.schemas import ImportCommitRequest
from fastapi_import_export.service import ImportExportService
from fastapi_import_export.storage_fs import ensure_dirs

SUMMARY_METRIC_KEYS: tuple[str, ...] = (
    "upload_parse_validate_median_seconds",
    "upload_parse_validate_p95_seconds",
    "preview_median_seconds",
    "preview_p95_seconds",
    "commit_median_seconds",
    "commit_p95_seconds",
    "total_median_seconds",
    "total_p95_seconds",
)


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Single benchmark run result.
    单次基准运行结果。

    Attributes:
        rows: Number of generated rows/生成行数。
        file_kind: Input file kind (csv/xlsx)/输入文件类型（csv/xlsx）。
        upload_parse_validate_seconds: Stage latency seconds/上传解析校验阶段耗时（秒）。
        preview_seconds: Stage latency seconds/预览阶段耗时（秒）。
        commit_seconds: Stage latency seconds/提交阶段耗时（秒）。
        total_seconds: End-to-end latency seconds/端到端总耗时（秒）。
        valid_rows: Number of valid rows/有效行数。
        error_rows: Number of error rows/错误行数。
    """

    rows: int
    file_kind: str
    upload_parse_validate_seconds: float
    preview_seconds: float
    commit_seconds: float
    total_seconds: float
    valid_rows: int
    error_rows: int


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    """Multi-round summary metrics.
    多轮汇总指标。

    Attributes:
        rounds: Number of rounds/轮次数。
        upload_parse_validate_median_seconds: Median of validate stage latency/校验阶段耗时中位数。
        upload_parse_validate_p95_seconds: P95 of validate stage latency/校验阶段耗时 P95。
        preview_median_seconds: Median of preview stage latency/预览阶段耗时中位数。
        preview_p95_seconds: P95 of preview stage latency/预览阶段耗时 P95。
        commit_median_seconds: Median of commit stage latency/提交阶段耗时中位数。
        commit_p95_seconds: P95 of commit stage latency/提交阶段耗时 P95。
        total_median_seconds: Median of end-to-end latency/端到端耗时中位数。
        total_p95_seconds: P95 of end-to-end latency/端到端耗时 P95。
    """

    rounds: int
    upload_parse_validate_median_seconds: float
    upload_parse_validate_p95_seconds: float
    preview_median_seconds: float
    preview_p95_seconds: float
    commit_median_seconds: float
    commit_p95_seconds: float
    total_median_seconds: float
    total_p95_seconds: float


class _DummyDB:
    """Simple benchmark db stub.
    简单基准 DB 桩对象。
    """

    async def rollback(self) -> None:
        """No-op rollback.
        空操作回滚。
        """
        return


def _generate_csv(path: Path, rows: int, *, seed: int | None = None) -> None:
    """Generate benchmark CSV fixture.
    生成基准测试 CSV 数据。

    Args:
        path: Destination file path/目标文件路径。
        rows: Number of data rows/数据行数。
        seed: Optional random seed for stable data generation/可选随机种子，用于稳定数据生成。
    """
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["name", "email", "age"])
        for _ in range(rows):
            user_id = rng.randint(100_000, 999_999)
            writer.writerow([f"user_{user_id}", f"user_{user_id}@example.com", 20 + (user_id % 30)])


def _generate_xlsx(path: Path, rows: int, *, seed: int | None = None) -> None:
    """Generate benchmark XLSX fixture.
    生成基准测试 XLSX 数据。

    Args:
        path: Destination file path/目标文件路径。
        rows: Number of data rows/数据行数。
        seed: Optional random seed for stable data generation/可选随机种子，用于稳定数据生成。
    """
    from openpyxl import Workbook

    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("Workbook.active is None / Workbook.active 为空")
    ws.append(["name", "email", "age"])
    for _ in range(rows):
        user_id = rng.randint(100_000, 999_999)
        ws.append([f"user_{user_id}", f"user_{user_id}@example.com", 20 + (user_id % 30)])
    wb.save(path)


def _build_upload_file(path: Path, content_type: str) -> UploadFile:
    """Build UploadFile from a local fixture file.
    从本地样例文件构造 UploadFile。

    Args:
        path: Fixture path/样例路径。
        content_type: MIME type/MIME 类型。

    Returns:
        UploadFile: Upload wrapper/上传文件对象。
    """
    payload = path.read_bytes()
    return UploadFile(
        filename=path.name,
        file=io.BytesIO(payload),
        size=len(payload),
        headers=Headers({"content-type": content_type}),
    )


async def _validate_pass(db: Any, df: Any, *, allow_overwrite: bool = False) -> tuple[Any, list[dict[str, Any]]]:
    """Pass-through validate handler.
    直通校验处理器。

    Args:
        db: Database object/数据库对象。
        df: Input dataframe/输入数据表。
        allow_overwrite: Overwrite flag/覆盖标志。

    Returns:
        tuple[Any, list[dict[str, Any]]]: Valid dataframe and errors/有效数据表与错误列表。
    """
    return df, []


async def _persist_pass(db: Any, valid_df: Any, *, allow_overwrite: bool = False) -> int:
    """Pass-through persist handler.
    直通持久化处理器。

    Args:
        db: Database object/数据库对象。
        valid_df: Validated dataframe/校验通过的数据表。
        allow_overwrite: Overwrite flag/覆盖标志。

    Returns:
        int: Imported rows/导入行数。
    """
    return int(valid_df.height)


async def run_benchmark(
    *,
    rows: int,
    file_kind: str,
    preview_page_size: int,
    base_dir: Path | None = None,
    seed: int | None = None,
) -> BenchmarkResult:
    """Run one benchmark case.
    运行一组基准用例。

    Args:
        rows: Number of generated rows/生成行数。
        file_kind: csv or xlsx/csv 或 xlsx。
        preview_page_size: Preview page size/预览分页大小。
        base_dir: Optional workspace root/可选工作目录。
        seed: Optional random seed for stable fixture generation/可选随机种子，用于稳定样例生成。

    Returns:
        BenchmarkResult: Benchmark metrics/基准指标。
    """
    if file_kind not in {"csv", "xlsx"}:
        raise ValueError("file_kind must be csv or xlsx / file_kind 必须为 csv 或 xlsx")

    with tempfile.TemporaryDirectory(prefix="fie-bench-") as temp_root:
        work_dir = base_dir or (Path(temp_root) / "workspace")
        config = ImportExportConfig(base_dir=work_dir)
        ensure_dirs(config=config)
        svc = ImportExportService(db=_DummyDB(), config=config)

        fixture_dir = Path(temp_root) / "fixtures"
        if file_kind == "csv":
            fixture = fixture_dir / "benchmark.csv"
            _generate_csv(fixture, rows, seed=seed)
            upload = _build_upload_file(fixture, "text/csv")
            column_aliases = {}
        else:
            fixture = fixture_dir / "benchmark.xlsx"
            _generate_xlsx(fixture, rows, seed=seed)
            upload = _build_upload_file(
                fixture,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            column_aliases = {}

        started = time.perf_counter()

        stage_started = time.perf_counter()
        validate_resp = await svc.upload_parse_validate(
            file=upload,
            column_aliases=column_aliases,
            validate_fn=_validate_pass,
        )
        upload_parse_validate_seconds = time.perf_counter() - stage_started

        stage_started = time.perf_counter()
        await svc.preview(
            import_id=validate_resp.import_id,
            checksum=validate_resp.checksum,
            page=1,
            page_size=preview_page_size,
            kind="valid",
        )
        preview_seconds = time.perf_counter() - stage_started

        stage_started = time.perf_counter()
        commit_resp = await svc.commit(
            body=ImportCommitRequest(import_id=validate_resp.import_id, checksum=validate_resp.checksum),
            persist_fn=_persist_pass,
        )
        commit_seconds = time.perf_counter() - stage_started

        total_seconds = time.perf_counter() - started

        return BenchmarkResult(
            rows=rows,
            file_kind=file_kind,
            upload_parse_validate_seconds=upload_parse_validate_seconds,
            preview_seconds=preview_seconds,
            commit_seconds=commit_seconds,
            total_seconds=total_seconds,
            valid_rows=commit_resp.imported_rows,
            error_rows=validate_resp.error_rows,
        )


def _percentile(values: list[float], ratio: float) -> float:
    """Compute percentile from a value list.
    从数值列表计算分位数。

    Args:
        values: Source values/输入数值。
        ratio: Percentile ratio in [0, 1]/分位比例（0 到 1）。

    Returns:
        float: Percentile value/分位数值。
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(ratio * len(ordered)) - 1))
    return float(ordered[index])


def _median(values: list[float]) -> float:
    """Compute median from values.
    从数值列表计算中位数。

    Args:
        values: Source values/输入数值。

    Returns:
        float: Median value/中位数值。
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) / 2.0)


def _result_payload(result: BenchmarkResult) -> dict[str, Any]:
    """Convert benchmark result to serializable payload.
    将基准结果转换为可序列化结构。

    Args:
        result: One round benchmark result/单轮基准结果。

    Returns:
        dict[str, Any]: Serializable run payload/可序列化的单轮结果。
    """
    return {
        "rows": result.rows,
        "file_kind": result.file_kind,
        "upload_parse_validate_seconds": round(result.upload_parse_validate_seconds, 6),
        "preview_seconds": round(result.preview_seconds, 6),
        "commit_seconds": round(result.commit_seconds, 6),
        "total_seconds": round(result.total_seconds, 6),
        "valid_rows": result.valid_rows,
        "error_rows": result.error_rows,
    }


def _summary_payload(summary: BenchmarkSummary) -> dict[str, float]:
    """Convert summary dataclass to serializable summary payload.
    将汇总数据类转换为可序列化的汇总结构。

    Args:
        summary: Benchmark summary/基准汇总。

    Returns:
        dict[str, float]: Serializable summary payload/可序列化汇总。
    """
    return {
        "upload_parse_validate_median_seconds": round(summary.upload_parse_validate_median_seconds, 6),
        "upload_parse_validate_p95_seconds": round(summary.upload_parse_validate_p95_seconds, 6),
        "preview_median_seconds": round(summary.preview_median_seconds, 6),
        "preview_p95_seconds": round(summary.preview_p95_seconds, 6),
        "commit_median_seconds": round(summary.commit_median_seconds, 6),
        "commit_p95_seconds": round(summary.commit_p95_seconds, 6),
        "total_median_seconds": round(summary.total_median_seconds, 6),
        "total_p95_seconds": round(summary.total_p95_seconds, 6),
    }


def _load_baseline_summary(path_text: str) -> dict[str, float]:
    """Load baseline summary from a JSON payload file.
    从 JSON 文件加载基线汇总。

    Args:
        path_text: Baseline json path/基线 JSON 路径。

    Returns:
        dict[str, float]: Baseline summary dictionary/基线汇总字典。

    Raises:
        ValueError: When baseline content is invalid/基线内容无效时抛出。
    """
    baseline_path = Path(path_text)
    if not baseline_path.exists():
        raise ValueError(f"baseline json not found: {baseline_path} / 基线文件不存在: {baseline_path}")
    data = json.loads(baseline_path.read_text(encoding="utf-8-sig"))
    raw_summary = data.get("summary") if isinstance(data, dict) else None
    if not isinstance(raw_summary, dict):
        raise ValueError("baseline json missing summary section / 基线 JSON 缺少 summary 节")
    baseline_summary: dict[str, float] = {}
    for key in SUMMARY_METRIC_KEYS:
        if key not in raw_summary:
            raise ValueError(f"baseline summary missing key: {key} / 基线 summary 缺少键: {key}")
        baseline_summary[key] = float(raw_summary[key])
    return baseline_summary


def _build_comparison(
    *,
    current_summary: dict[str, float],
    baseline_summary: dict[str, float],
    threshold_ratio: float,
) -> dict[str, Any]:
    """Build comparison report between current and baseline summary.
    构建当前结果与基线结果的对比报告。

    Args:
        current_summary: Current summary payload/当前汇总结果。
        baseline_summary: Baseline summary payload/基线汇总结果。
        threshold_ratio: Allowed regression ratio/允许的退化比例。

    Returns:
        dict[str, Any]: Comparison report with regression list/包含退化项列表的对比报告。
    """
    regressions: list[dict[str, Any]] = []
    metric_deltas: dict[str, dict[str, float]] = {}
    for key in SUMMARY_METRIC_KEYS:
        current = float(current_summary[key])
        baseline = float(baseline_summary[key])
        if baseline <= 0:
            ratio = 0.0 if current <= 0 else float("inf")
        else:
            ratio = (current - baseline) / baseline
        metric_deltas[key] = {
            "baseline": round(baseline, 6),
            "current": round(current, 6),
            "delta_ratio": round(ratio, 6) if math.isfinite(ratio) else float("inf"),
        }
        if ratio > threshold_ratio:
            regressions.append(
                {
                    "metric": key,
                    "baseline": round(baseline, 6),
                    "current": round(current, 6),
                    "delta_ratio": round(ratio, 6) if math.isfinite(ratio) else float("inf"),
                }
            )
    return {
        "threshold_ratio": float(threshold_ratio),
        "passed": len(regressions) == 0,
        "regression_count": len(regressions),
        "regressions": regressions,
        "metric_deltas": metric_deltas,
    }


def _build_summary(results: list[BenchmarkResult]) -> BenchmarkSummary:
    """Build median/p95 summary from multi-round results.
    从多轮结果构建 median/p95 汇总。

    Args:
        results: Per-round benchmark results/每轮基准结果。

    Returns:
        BenchmarkSummary: Summary metrics/汇总指标。
    """
    validate_values = [float(item.upload_parse_validate_seconds) for item in results]
    preview_values = [float(item.preview_seconds) for item in results]
    commit_values = [float(item.commit_seconds) for item in results]
    total_values = [float(item.total_seconds) for item in results]
    return BenchmarkSummary(
        rounds=len(results),
        upload_parse_validate_median_seconds=_median(validate_values),
        upload_parse_validate_p95_seconds=_percentile(validate_values, 0.95),
        preview_median_seconds=_median(preview_values),
        preview_p95_seconds=_percentile(preview_values, 0.95),
        commit_median_seconds=_median(commit_values),
        commit_p95_seconds=_percentile(commit_values, 0.95),
        total_median_seconds=_median(total_values),
        total_p95_seconds=_percentile(total_values, 0.95),
    )


async def run_benchmark_rounds(
    *,
    rows: int,
    file_kind: str,
    preview_page_size: int,
    rounds: int,
    warmup: int = 0,
    seed: int | None = None,
) -> tuple[list[BenchmarkResult], BenchmarkSummary]:
    """Run benchmark for multiple rounds and return summary.
    执行多轮基准并返回汇总结果。

    Args:
        rows: Number of generated rows/生成行数。
        file_kind: csv or xlsx/csv 或 xlsx。
        preview_page_size: Preview page size/预览分页大小。
        rounds: Number of benchmark rounds/基准轮次数。
        warmup: Warmup rounds excluded from statistics/不计入统计的预热轮次数。
        seed: Optional random seed for stable fixture generation/可选随机种子，用于稳定样例生成。

    Returns:
        tuple[list[BenchmarkResult], BenchmarkSummary]: Runs and summary/单轮结果与汇总结果。
    """
    if rounds < 1:
        raise ValueError("rounds must be >= 1 / rounds 必须 >= 1")
    if warmup < 0:
        raise ValueError("warmup must be >= 0 / warmup 必须 >= 0")

    # Warmup rounds are intentionally discarded from final stats.
    # 预热轮仅用于稳定运行状态，不计入最终统计。
    for warmup_index in range(warmup):
        round_seed = None if seed is None else int(seed + warmup_index)
        await run_benchmark(rows=rows, file_kind=file_kind, preview_page_size=preview_page_size, seed=round_seed)

    results: list[BenchmarkResult] = []
    for round_index in range(rounds):
        round_seed = None if seed is None else int(seed + warmup + round_index)
        one = await run_benchmark(rows=rows, file_kind=file_kind, preview_page_size=preview_page_size, seed=round_seed)
        results.append(one)
    return results, _build_summary(results)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.
    解析命令行参数。

    Returns:
        argparse.Namespace: Parsed args/解析后的参数。
    """
    parser = argparse.ArgumentParser(
        description="ImportExportService benchmark scaffold / ImportExportService 性能基准脚手架"
    )
    parser.add_argument("--rows", type=int, default=10000, help="Generated rows / 生成行数")
    parser.add_argument("--kind", choices=["csv", "xlsx"], default="csv", help="Input file kind / 输入文件类型")
    parser.add_argument("--preview-page-size", type=int, default=100, help="Preview page size / 预览分页大小")
    parser.add_argument("--rounds", type=int, default=1, help="Benchmark rounds / 基准轮次数")
    parser.add_argument("--warmup", type=int, default=0, help="Warmup rounds (excluded) / 预热轮次数（不计入统计）")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for stable generation / 稳定生成的随机种子")
    parser.add_argument("--baseline-json", type=str, default="", help="Baseline JSON path / 基线 JSON 路径")
    parser.add_argument(
        "--regression-threshold",
        type=float,
        default=0.05,
        help="Allowed regression ratio (0.05 = 5%%) / 允许退化比例（0.05=5%%）",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit non-zero when regression detected / 发现退化时返回非 0 退出码",
    )
    parser.add_argument(
        "--export-json",
        type=str,
        default="",
        help="Write result JSON to file path / 将结果 JSON 写入文件路径",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output / 输出 JSON")
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint.
    命令行入口。

    Returns:
        int: Exit code/退出码。
    """
    args = parse_args()
    threshold_ratio = float(args.regression_threshold)
    if threshold_ratio < 0:
        print("regression-threshold must be >= 0 / regression-threshold 必须 >= 0")
        return 2
    runs, summary = asyncio.run(
        run_benchmark_rounds(
            rows=int(args.rows),
            file_kind=str(args.kind),
            preview_page_size=int(args.preview_page_size),
            rounds=int(args.rounds),
            warmup=int(args.warmup),
            seed=int(args.seed),
        )
    )
    payload = {
        "config": {
            "rows": int(args.rows),
            "file_kind": str(args.kind),
            "preview_page_size": int(args.preview_page_size),
            "rounds": int(args.rounds),
            "warmup": int(args.warmup),
            "seed": int(args.seed),
            "baseline_json": str(args.baseline_json),
            "regression_threshold": threshold_ratio,
            "fail_on_regression": bool(args.fail_on_regression),
        },
        "summary": _summary_payload(summary),
        "runs": [_result_payload(item) for item in runs],
    }

    baseline_json_path = str(args.baseline_json).strip()
    comparison: dict[str, Any] | None = None
    if baseline_json_path:
        baseline_summary = _load_baseline_summary(baseline_json_path)
        comparison = _build_comparison(
            current_summary=payload["summary"],
            baseline_summary=baseline_summary,
            threshold_ratio=threshold_ratio,
        )
        payload["comparison"] = comparison

    if bool(args.fail_on_regression) and comparison is None:
        print("fail-on-regression requires --baseline-json / fail-on-regression 需要 --baseline-json")
        return 2

    export_json_path = str(args.export_json).strip()
    if export_json_path:
        out_path = Path(export_json_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if bool(args.json):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("Benchmark Summary / 基准汇总")
        for key, value in payload["config"].items():
            print(f"- config.{key}: {value}")
        for key, value in payload["summary"].items():
            print(f"- summary.{key}: {value}")
        print("Benchmark Runs / 单轮结果")
        for idx, run in enumerate(payload["runs"], start=1):
            print(f"  Round {idx} / 第 {idx} 轮")
            for key, value in run.items():
                print(f"  - {key}: {value}")

        if comparison is not None:
            print("Benchmark Comparison / 基线对比")
            print(f"- comparison.threshold_ratio: {comparison['threshold_ratio']}")
            print(f"- comparison.passed: {comparison['passed']}")
            print(f"- comparison.regression_count: {comparison['regression_count']}")
            if comparison["regressions"]:
                for item in comparison["regressions"]:
                    print(
                        "- regression: "
                        f"metric={item['metric']}, baseline={item['baseline']}, "
                        f"current={item['current']}, delta_ratio={item['delta_ratio']}"
                    )

    if bool(args.fail_on_regression) and comparison is not None and not bool(comparison["passed"]):
        print("Regression detected, CI gate failed / 检测到性能退化，CI 门禁失败")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
