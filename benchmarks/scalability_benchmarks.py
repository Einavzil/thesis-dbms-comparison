""" Scalability benchmarks S1 : R1, W1 under increasing concurrency"""
import sys
import os
import time
import threading
from datetime import datetime, timezone
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from concurrent.futures import ThreadPoolExecutor
from config import get_pg_connection, get_mongo_database, USER_ID, POST_ID
from utils import save_scalability_results
import cleanups

results_lock = threading.Lock()
CONCURRENCY_LEVELS = [1, 5, 10, 25, 50]
DURATION_SECONDS = 300

PG_R1 = """
    SELECT u.id, u.displayName, u.reputation,
    p.id, p.title, p.score, p.creationDate
    FROM users u
    JOIN posts p ON p.ownerUserId = u.id
    WHERE u.id = %s
    ORDER BY p.creationDate DESC
    LIMIT 20;
    """

PG_W1 = """
    INSERT INTO comments (postId, userId, score, text, creationDate)
    VALUES (%s, %s, 0, %s, %s);
    """

PG_W1_UPDATE_COMMENT_COUNT = """
    UPDATE posts
    SET commentCount = COALESCE(commentCount, 0) + 1
    WHERE id = %s;
    """

def pg_worker(operation, stop_event, results, conn_factory):
    conn = conn_factory()

    try:
        while not stop_event.is_set():
            start = time.perf_counter()
            try:
                with conn.cursor() as cur:
                    if operation == "R1":
                        cur.execute(PG_R1, (USER_ID,))
                        cur.fetchall()
                    elif operation == "W1":
                        cur.execute(PG_W1, (POST_ID, USER_ID, "S1 test comment", datetime.now(timezone.utc).replace(tzinfo=None)))
                        cur.execute(PG_W1_UPDATE_COMMENT_COUNT, (POST_ID,))
                        conn.commit()
                duration = (time.perf_counter() - start) * 1000  # ms
                with results_lock:
                    results.append(duration)
            except Exception as e:
                print(f"Error occurred in PG worker: {e}")
                conn.rollback()
    finally:
        conn.close()

def mongo_worker(operation, stop_event, results, db_factory):
    db = db_factory()

    try:
        while not stop_event.is_set():
            start = time.perf_counter()
            try:
                if operation == "R1":
                    db.users.find_one({ "_id": USER_ID}, { "displayName": 1, "reputation": 1 })
                    list(db.posts.find(
                        { "ownerUserId": USER_ID },
                        { "title": 1, "score": 1, "creationDate": 1 }
                        ).sort([("creationDate", -1)]).limit(20))
                elif operation == "W1":
                    comment_id = get_next_sequence(db, "commentId")
                    result = db.posts.update_one(
                        { "_id": POST_ID },
                        { "$push": { "comments": {
                                "id": comment_id,
                                "userId": USER_ID,
                                "score": 0,
                                "text": "S1 test comment",
                                "creationDate": datetime.now(timezone.utc).replace(tzinfo=None)
                        }},
                        "$inc": { "commentCount": 1 }
                        }
                    )
                    if result.matched_count == 0:
                        print(f"Warning: Post with _id {POST_ID} not found for W1 operation.")
                duration = (time.perf_counter() - start) * 1000  # ms

                with results_lock:
                    results.append(duration)
            except Exception as e:
                print(f"Error occurred in MongoDB worker: {e}")
    finally:
        db.client.close()

def run_scalability(db_name, operation, concurrency, worker_func, factory):
    results = []
    stop_event = threading.Event()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(worker_func, operation, stop_event, results, factory)
            for _ in range(concurrency)
        ]

        time.sleep(DURATION_SECONDS)
        stop_event.set()

        for future in futures:
            future.result()  

    save_scalability_results(f"S1_{operation}", db_name, concurrency, results, DURATION_SECONDS)

    if operation == "W1":
        if db_name == "postgres":
            conn = get_pg_connection()
            try:
                cleanups.pg_s1_w1_cleanup(conn)
            finally:
                conn.close()
        else:
            db = get_mongo_database()
            try:
                cleanups.mongo_s1_w1_cleanup(db)
            finally:
                db.client.close()
    
# get next IDs for comments and posts in mongo
def get_next_sequence(db, name):
    result = db.counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        return_document=True
    )
    return result["seq"]
        
def main():
    print("Starting scalability tests...\n")
    for concurrency in CONCURRENCY_LEVELS:
        print(f"Concurrency level: {concurrency} threads")
        run_scalability("postgres", "R1", concurrency, pg_worker, get_pg_connection)
        run_scalability("postgres", "W1", concurrency, pg_worker, get_pg_connection)
        run_scalability("mongodb", "R1", concurrency, mongo_worker, get_mongo_database)
        run_scalability("mongodb", "W1", concurrency, mongo_worker, get_mongo_database)

if __name__ == "__main__":
    main()
