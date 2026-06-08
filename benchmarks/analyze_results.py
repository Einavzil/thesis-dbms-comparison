import os
import csv
import numpy as np

from utils import calculate_stats
from config import RESULTS_DIR
RUNS = [1, 2, 3]
OPERATIONS = {
    "read": ["R1", "R2", "R3", "R4"],
    "write": ["W1", "W2", "W3", "W4"],
}
DATABASES = ["postgres", "mongodb"]
OUTPUT_DIR = "results/analysis_results"


# load raw iteration times from CSV files
def load_raw_times(benchmark, run, operation, database):
    filepath = os.path.join(RESULTS_DIR, benchmark, f"run{run}", f"{operation}_{database}.csv")
    if not os.path.exists(filepath):
        print(f"File {filepath} does not exist.")
        return []
    
    times = []
    with open(filepath, "r") as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            times.append(float(row[3]))
    return times

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for benchmark, operations in OPERATIONS.items():
        output_filepath = os.path.join(OUTPUT_DIR, f"{benchmark}_summary.csv")
        with open(output_filepath, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["operation", "database", "mean", "median", "p95", "p99", "stddev"])
            for operation in operations:
                for database in DATABASES:
                    all_times = []
                    for run in RUNS:
                        times = load_raw_times(benchmark, run, operation, database)
                        all_times.extend(times)
                    
                    if not all_times:
                        print(f"No data found for {operation} on {database} in {benchmark}. Skipping.")
                        continue
                    
                    stats = calculate_stats(all_times)
                    writer.writerow([operation, database, stats["mean"], stats["median"], 
                                     stats["p95"], stats["p99"], stats["stddev"]])
                    print(f"{operation} ({database}): {stats}")

if __name__ == "__main__":
    main()
