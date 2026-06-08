""" Configuration for database connections and benchmark settings. """

import psycopg2
from pymongo import MongoClient

POSTGRES_CONFIG = {
    "dbname": "stackoverflow",
    "user": "thesis",
    "password": "thesis",
    "host": "localhost",
    "port": "5432",
    "connect_timeout": 10,
}

MONGO_CONFIG = "mongodb://thesis:thesis@localhost:27017/stackoverflow?authSource=admin"

ITERATIONS = 100
WARMUP = 10
CONSISTENCY_ITERATIONS = 100
RESULTS_DIR = "results/raw"

USER_ID = 816291 # Umesh Shankar, post count of 100
POST_ID = 859212 # question post, 30 comments, score 68

def get_pg_connection():
    return psycopg2.connect(**POSTGRES_CONFIG)

def get_mongo_database():
    client = MongoClient(MONGO_CONFIG)
    return client["stackoverflow"]
