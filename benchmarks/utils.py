import os
import time
import csv
import numpy as np
from config import RESULTS_DIR


def measure(op_func, iterations, warmup):
    # Warmup phase
    for _ in range(warmup):
        op_func()

    times = []

    for _ in range(iterations):
        start_time = time.perf_counter()
        op_func()
        end_time = time.perf_counter()
        times.append((end_time - start_time) * 1000) # convert to ms

    return times

def measure_with_cleanup(op_func, cleanup_func, iterations, warmup):
    # warmup phase
    for _ in range(warmup):
        data = op_func()
        cleanup_func(data)

    times = []

    for _ in range(iterations):
        start_time = time.perf_counter()
        data = op_func()
        end_time = time.perf_counter()

        times.append((end_time - start_time) * 1000) # convert to ms
        cleanup_func(data)

    return times


def calculate_stats(times):
    return {
        "mean": float(round(np.mean(times), 4)),
        "median": float(round(np.median(times), 4)),
        "p95": float(round(np.percentile(times, 95), 4)),
        "p99": float(round(np.percentile(times, 99), 4)),
        "stddev": float(round(np.std(times), 4))
    }

def save_results(operation, database, times):
    result_folder = "write" if operation.startswith("W") else "read"
    result_dir = os.path.join(RESULTS_DIR, result_folder, "run3")
    os.makedirs(result_dir, exist_ok=True)
    filepath = os.path.join(result_dir, f"{operation}_{database}.csv")

    with open(filepath, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["operation", "database", "iteration", "time_ms"])
        for i, t in enumerate(times, 1):
            writer.writerow([operation, database, i, round(t, 4)])

    stats = calculate_stats(times)

    summary_filepath = os.path.join(result_dir, f"{operation}_{database}_summary.csv")
    with open(summary_filepath, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["operation", "database", "mean", "median", "p95", "p99", "stddev"])
        writer.writerow([operation, database, stats["mean"], stats["median"], stats["p95"], stats["p99"], stats["stddev"]])
    
    print(f"{operation} ({database}): {stats}")
    return stats

def save_scalability_results(operation, database, concurrency, results, duration_seconds):
    result_dir = os.path.join(RESULTS_DIR, "scalability")
    os.makedirs(result_dir, exist_ok=True)
    filepath = os.path.join(result_dir, f"{operation}_{database}_{concurrency}.csv")

    total_ops = len(results)
    throughput = round(total_ops / duration_seconds, 4)
    if results:
        stats = calculate_stats(results)
    else:
        stats = {"mean": 0, "median": 0, "p95": 0, "p99": 0, "stddev": 0}

    with open(filepath, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["operation", "database", "concurrency", "total_ops",
                        "mean_latency_ms", "median_ms", "p95_ms", "p99_ms",
                        "stddev_ms", "throughput_ops_sec"])
        writer.writerow([operation, database, concurrency, total_ops,
                        stats["mean"], stats["median"], stats["p95"], 
                        stats["p99"], stats["stddev"], throughput])

    print(f"{operation} ({database}, {concurrency} threads) completed with {total_ops} ops, "
          f"throughput: {throughput} ops/sec, mean: {stats['mean']}ms, median: {stats['median']}ms,"
          f" p95: {stats['p95']}ms, p99: {stats['p99']}ms, stddev: {stats['stddev']}ms")
    
def save_consistency_results(operation, database, correct, total):
    result_dir = os.path.join(RESULTS_DIR, "consistency")
    os.makedirs(result_dir, exist_ok=True)
    proportion  = round(correct / total * 100, 2)
    filepath = os.path.join(result_dir, f"{operation}_{database}.csv")

    with open(filepath, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["operation", "database", "correct", "total", "proportion_correct"])
        writer.writerow([operation, database, correct, total, proportion])

    print(f"{operation} ({database}): {correct}/{total} correct ({proportion}%)")
