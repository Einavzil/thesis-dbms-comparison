import csv
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    from matplotlib.ticker import StrMethodFormatter
except ImportError as exc:
    raise SystemExit(
        "Matplotlib is required. Install it with:\n"
        "venv\\Scripts\\python -m pip install matplotlib"
    ) from exc


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCALABILITY_RESULTS_DIR = PROJECT_DIR / "results" / "raw" / "scalability"
ANALYSIS_RESULTS_DIR = PROJECT_DIR / "results" / "analysis_results"
OUTPUT_DIR = PROJECT_DIR / "results" / "figures"
CONCURRENCY_LEVELS = [1, 5, 10, 25, 50]

DATABASES = {
    "postgres": {"label": "PostgreSQL", "color": "#2F6B9A"},
    "mongodb": {"label": "MongoDB", "color": "#4F8A5B"},
}

FIGURES = {
    "S1_R1": "figure_5_read_scalability.png",
    "S1_W1": "figure_6_write_scalability.png",
}


def load_results(operation, database):
    results = []

    for concurrency in CONCURRENCY_LEVELS:
        path = SCALABILITY_RESULTS_DIR / f"{operation}_{database}_{concurrency}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing scalability result file: {path}")

        with path.open(newline="", encoding="utf-8") as csv_file:
            row = next(csv.DictReader(csv_file))

        results.append(
            {
                "mean_latency_ms": float(row["mean_latency_ms"]),
                "throughput_ops_sec": float(row["throughput_ops_sec"]),
            }
        )

    return results


def create_figure(operation, output_name):
    data = {
        database: load_results(operation, database)
        for database in DATABASES
    }

    figure, axes = plt.subplots(
        nrows=1,
        ncols=2,
        figsize=(10.5, 4.2),
        constrained_layout=True,
    )

    panels = [
        ("mean_latency_ms", "Mean latency", "Mean latency (ms)", "{x:,.1f}"),
        (
            "throughput_ops_sec",
            "Throughput",
            "Throughput (operations/s)",
            "{x:,.0f}",
        ),
    ]

    for axis, (metric, title, y_label, number_format) in zip(axes, panels):
        for database, style in DATABASES.items():
            values = [result[metric] for result in data[database]]
            axis.plot(
                CONCURRENCY_LEVELS,
                values,
                label=style["label"],
                color=style["color"],
                linewidth=2,
                marker="o",
                markersize=5,
            )

        axis.set_title(title, fontsize=11, fontweight="bold")
        axis.set_xlabel("Concurrent worker threads", fontsize=10)
        axis.set_ylabel(y_label, fontsize=10)
        axis.set_xticks(CONCURRENCY_LEVELS)
        axis.yaxis.set_major_formatter(StrMethodFormatter(number_format))
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.8)
        axis.set_axisbelow(True)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.tick_params(labelsize=9)

    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.02),
        ncols=2,
        frameon=False,
        fontsize=10,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / output_name
    figure.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Created {output_path}")


def load_latency_summary(benchmark):
    path = ANALYSIS_RESULTS_DIR / f"{benchmark}_summary.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing analysis result file: {path}")

    results = {}
    with path.open(newline="", encoding="utf-8") as csv_file:
        for row in csv.DictReader(csv_file):
            results.setdefault(row["operation"], {})[row["database"]] = float(
                row["mean"]
            )

    return results


def create_latency_bar_chart(benchmark, output_name):
    data = load_latency_summary(benchmark)
    operations = sorted(data)
    positions = list(range(len(operations)))
    bar_width = 0.36

    figure, axis = plt.subplots(figsize=(8, 4.5), constrained_layout=True)

    for offset, (database, style) in zip(
        (-bar_width / 2, bar_width / 2),
        DATABASES.items(),
    ):
        values = [data[operation][database] for operation in operations]
        bars = axis.bar(
            [position + offset for position in positions],
            values,
            width=bar_width,
            label=style["label"],
            color=style["color"],
        )
        axis.bar_label(bars, fmt="%.2f", padding=3, fontsize=9)

    axis.set_xlabel("Benchmark operation", fontsize=10)
    axis.set_ylabel("Mean latency (ms)", fontsize=10)
    axis.set_xticks(positions, operations)
    axis.grid(axis="y", color="#D9D9D9", linewidth=0.8)
    axis.set_axisbelow(True)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.tick_params(labelsize=9)
    axis.legend(frameon=False, fontsize=10)
    axis.margins(y=0.12)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / output_name
    figure.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    print(f"Created {output_path}")


def main():
    create_latency_bar_chart(
        "read",
        "figure_3_read_mean_latency.png",
    )
    create_latency_bar_chart(
        "write",
        "figure_4_write_mean_latency.png",
    )

    for operation, output_name in FIGURES.items():
        create_figure(operation, output_name)


if __name__ == "__main__":
    main()
