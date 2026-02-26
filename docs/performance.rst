Performance
===========

This page describes the performance benchmark scaffold for ``ImportExportService``.
本页说明 ``ImportExportService`` 的性能基准脚手架。

Scope
-----

Current scaffold measures three lifecycle stages:
当前脚手架覆盖三个生命周期阶段：

- ``upload_parse_validate``
- ``preview``
- ``commit``

The benchmark script is intentionally lightweight and non-invasive.
该基准脚本设计为轻量、非侵入，不影响主库运行路径。

Benchmark Script
----------------

Location:

- ``benchmarks/benchmark_import_service.py``

Run CSV benchmark:

.. code-block:: bash

   python benchmarks/benchmark_import_service.py --kind csv --rows 10000

Run XLSX benchmark:

.. code-block:: bash

   python benchmarks/benchmark_import_service.py --kind xlsx --rows 10000

Run JSON output:

.. code-block:: bash

   python benchmarks/benchmark_import_service.py --kind csv --rows 50000 --json

Run multi-round benchmark (median/p95):

.. code-block:: bash

   python benchmarks/benchmark_import_service.py --kind csv --rows 50000 --rounds 5 --json

Run benchmark with warmup rounds (excluded from summary):

.. code-block:: bash

   python benchmarks/benchmark_import_service.py --kind csv --rows 50000 --warmup 2 --rounds 5 --json

Run benchmark with fixed seed (cross-machine reproducibility):

.. code-block:: bash

   python benchmarks/benchmark_import_service.py --kind csv --rows 50000 --seed 42 --warmup 2 --rounds 5 --json

Export JSON result to file (for CI history tracking):

.. code-block:: bash

   python benchmarks/benchmark_import_service.py --kind csv --rows 50000 --seed 42 --warmup 2 --rounds 5 --export-json .perf/latest.json

Compare with baseline JSON and print comparison:

.. code-block:: bash

   python benchmarks/benchmark_import_service.py --kind csv --rows 50000 --seed 42 --warmup 2 --rounds 5 --baseline-json .perf/baseline.json --json

Enable CI regression gate (non-zero exit on regression):

.. code-block:: bash

   python benchmarks/benchmark_import_service.py --kind csv --rows 50000 --seed 42 --warmup 2 --rounds 5 --baseline-json .perf/baseline.json --regression-threshold 0.05 --fail-on-regression --export-json .perf/latest.json

Output Structure
----------------

The script outputs three sections:
脚本输出分为三个部分：

- ``config``: run configuration / 运行配置
- ``summary``: median/p95 summary metrics / median/p95 汇总指标
- ``runs``: per-round raw metrics / 每轮原始指标

``config`` includes:

- ``warmup``: warmup rounds excluded from summary / 不计入汇总统计的预热轮次数
- ``seed``: random seed for stable fixture generation / 用于稳定样例生成的随机种子
- ``baseline_json``: baseline result json path / 基线结果 JSON 路径
- ``regression_threshold``: allowed regression ratio / 允许的退化比例
- ``fail_on_regression``: CI gate switch / CI 门禁开关

CLI export option:

- ``--export-json``: write the full payload to a target file / 将完整结果写入目标文件

Comparison and gate options:

- ``--baseline-json``: compare current summary with baseline summary / 使用基线汇总对比当前结果
- ``--regression-threshold``: allowed regression ratio (default 0.05) / 允许退化比例（默认 0.05）
- ``--fail-on-regression``: return non-zero when regressions exceed threshold / 超阈值退化时返回非 0

CI Workflow
-----------

Project workflow:

- ``.github/workflows/performance-gate.yml``

Default CI gate behavior:

- Uses ``.perf/baseline.json`` as baseline input.
- Runs benchmark script with seed/warmup/rounds.
- Fails pull request when regressions exceed threshold.
- Workflow example uses ``--regression-threshold 0.30``; tune by runner noise and team policy.
   workflow 示例使用 ``--regression-threshold 0.30``，可按 runner 抖动与团队策略调整。
- Uploads ``.perf/latest-ci.json`` as artifact for diagnostics.

``summary`` fields:

- ``upload_parse_validate_median_seconds`` / ``upload_parse_validate_p95_seconds``
- ``preview_median_seconds`` / ``preview_p95_seconds``
- ``commit_median_seconds`` / ``commit_p95_seconds``
- ``total_median_seconds`` / ``total_p95_seconds``

``runs`` fields (each round):

- ``rows``: generated row count / 生成行数
- ``file_kind``: input format / 输入格式
- ``upload_parse_validate_seconds``: validate stage latency / 校验阶段耗时
- ``preview_seconds``: preview stage latency / 预览阶段耗时
- ``commit_seconds``: commit stage latency / 提交阶段耗时
- ``total_seconds``: end-to-end latency / 端到端总耗时
- ``valid_rows``: committed row count / 提交成功行数
- ``error_rows``: validation error row count / 校验错误行数

Recommended Matrix
------------------

Suggested row scales:
建议行数规模：

- 10k (baseline / 基线)
- 50k (medium / 中等)
- 100k (large / 大规模)

Suggested dimensions:
建议维度：

- format: CSV / XLSX
- overwrite mode: reject / upsert / replace
- preview page size: 100 / 500

Notes
-----

- This scaffold uses a dummy db persistence handler by default.
  该脚手架默认使用虚拟 DB 持久化处理器。
- To benchmark real DB latency, replace ``_persist_pass`` with your production-like persist function.
  若要评估真实数据库性能，请将 ``_persist_pass`` 替换为接近生产的持久化函数。
- For stable results, run multiple rounds and report median/p95.
  为获得稳定结论，请多轮运行并记录 median/p95。
- Use ``--warmup`` (for example 1-3 rounds) to reduce cold-start noise.
   建议使用 ``--warmup``（例如 1-3 轮）减少冷启动抖动。
- Use ``--seed`` to make generated datasets deterministic and easier to compare across machines.
   建议使用 ``--seed`` 固定生成数据，提升跨机器对比稳定性。
- Keep only ``.perf/baseline.json`` in git; ignore other ``.perf`` artifacts.
   建议仅提交 ``.perf/baseline.json``，其余 ``.perf`` 产物应忽略。
