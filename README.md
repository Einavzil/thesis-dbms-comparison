# PostgreSQL vs MongoDB Thesis Benchmark

This repository contains the benchmark implementation for the bachelor thesis:

**A Comparative Analysis of SQL and NoSQL Database Trade-Offs in High-Volume Social Media Transactional Systems**

It compares PostgreSQL 16 and MongoDB 7 using read, write, scalability, and consistency operations derived from social media workloads.

## Dataset

The project uses the Math Stack Exchange subset of the [Stack Exchange Public Data Dump](https://archive.org/details/stackexchange). The dataset is not included because of its size.

Create a new folder in the project root (outside of the repository folder), call it "datadump-project" and place the extracted XML dataset files in it.
A project structure should look like this:

```text
project-root/
├── datadump-project/
└── dbms-comparison-project/
```

## Setup

From `dbms-comparison-project`:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
docker compose up -d
```

Load the databases:

```powershell
venv\Scripts\python init\init_postgres.py
venv\Scripts\python init\init_mongo.py
```

## Run Benchmarks

```powershell
venv\Scripts\python benchmarks\read_benchmarks.py
venv\Scripts\python benchmarks\write_benchmarks.py
venv\Scripts\python benchmarks\scalability_benchmarks.py
venv\Scripts\python benchmarks\consistency_benchmarks.py
```

The isolated read and write benchmarks use 10 warm-up operations and 100 measured iterations. Scalability tests run R1 and W1 for 300 seconds using 1, 5, 10, 25, and 50 worker threads.

## Analysis and Figures

```powershell
venv\Scripts\python benchmarks\analyze_results.py
venv\Scripts\python benchmarks\generate_scalability_figures.py
```

Results are written to the `results` directory.

## Scope

The benchmark uses standalone PostgreSQL and MongoDB instances on one host. It does not evaluate replication, network partitions, or distributed horizontal scaling.
