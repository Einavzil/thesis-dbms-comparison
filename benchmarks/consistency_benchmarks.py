"""Consistency Benchmarks: C1, C2"""

import os
import sys
import threading
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_pg_connection, get_mongo_database, CONSISTENCY_ITERATIONS, USER_ID, POST_ID
from utils import save_consistency_results
import cleanups


def get_next_sequence(db, name):
    result = db.counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        return_document=True
    )
    return result["seq"]


def run_pg_c1():
    control_conn = get_pg_connection()
    conn1 = get_pg_connection()
    conn2 = get_pg_connection()
    original_score = None
    correct = 0

    def increment_score(conn, barrier):
        barrier.wait()
        with conn.cursor() as cur:
            cur.execute("UPDATE posts SET score = score + 1 WHERE id = %s;", (POST_ID,))
        conn.commit()

    try:
        with control_conn.cursor() as cur:
            cur.execute("SELECT score FROM posts WHERE id = %s;", (POST_ID,))
            original_score = cur.fetchone()[0]
            for i in range(CONSISTENCY_ITERATIONS):
                cur.execute("UPDATE posts SET score = 0 WHERE id = %s;", (POST_ID,))
                control_conn.commit()
                barrier = threading.Barrier(2)
                t1 = threading.Thread(target=increment_score, args=(conn1, barrier))
                t2 = threading.Thread(target=increment_score, args=(conn2, barrier))
                t1.start()
                t2.start()
                t1.join()
                t2.join()

                cur.execute("SELECT score FROM posts WHERE id = %s;", (POST_ID,))
                final_score = cur.fetchone()[0]
                if final_score == 2:
                    correct += 1

                if (i + 1) % 10 == 0:
                    print(f"  C1 (postgres): {i + 1}/{CONSISTENCY_ITERATIONS}")
    finally:
        if original_score is not None:
            with control_conn.cursor() as cur:
                cur.execute("UPDATE posts SET score = %s WHERE id = %s;", (original_score, POST_ID))
            control_conn.commit()
        control_conn.close()
        conn1.close()
        conn2.close()

    return correct


def run_mongo_c1():
    control_db = get_mongo_database()
    db1 = get_mongo_database()
    db2 = get_mongo_database()
    original_score = None
    correct = 0

    def increment_score(db, barrier):
        barrier.wait()
        db.posts.update_one({"_id": POST_ID}, {"$inc": {"score": 1}})

    try:
        original_post = control_db.posts.find_one({"_id": POST_ID}, {"score": 1})
        original_score = original_post["score"] if original_post else None

        for i in range(CONSISTENCY_ITERATIONS):
            control_db.posts.update_one({"_id": POST_ID}, {"$set": {"score": 0}})

            barrier = threading.Barrier(2)
            t1 = threading.Thread(target=increment_score, args=(db1, barrier))
            t2 = threading.Thread(target=increment_score, args=(db2, barrier))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            post = control_db.posts.find_one({"_id": POST_ID}, {"score": 1})
            if post["score"] == 2:
                correct += 1

            if (i + 1) % 10 == 0:
                print(f"  C1 (mongodb): {i + 1}/{CONSISTENCY_ITERATIONS}")
    finally:
        if original_score is not None:
            control_db.posts.update_one({"_id": POST_ID}, {"$set": {"score": original_score}})
        control_db.client.close()
        db1.client.close()
        db2.client.close()

    return correct


def pg_c2_once():
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO comments (postId, userId, score, text, creationDate)
                VALUES (%s, %s, 0, %s, %s)
                RETURNING id;
                """,
                (POST_ID, USER_ID, "C2 test comment", datetime.now(timezone.utc).replace(tzinfo=None))
            )
            comment_id = cur.fetchone()[0]
            cur.execute(
                "UPDATE posts SET commentCount = COALESCE(commentCount, 0) + 1 WHERE id = %s;",
                (POST_ID,)
            )
            conn.commit()

            cur.execute(
                "SELECT id FROM comments WHERE id = %s AND postId = %s;",
                (comment_id, POST_ID)
            )
            is_visible = cur.fetchone() is not None
            cleanups.pg_c2_cleanup(conn, comment_id)
            return is_visible
    finally:
        conn.close()


def mongo_c2_once():
    db = get_mongo_database()
    try:
        comment_id = get_next_sequence(db, "commentId")
        comment = {
            "id": comment_id,
            "userId": USER_ID,
            "score": 0,
            "text": "C2 test comment",
            "creationDate": datetime.now(timezone.utc).replace(tzinfo=None)
        }
        db.posts.update_one(
            {"_id": POST_ID},
            {"$push": {"comments": comment}, "$inc": {"commentCount": 1}}
        )
        post = db.posts.find_one(
            {"_id": POST_ID, "comments": {"$elemMatch": {"id": comment_id}}},
            {"comments": {"$elemMatch": {"id": comment_id}}}
        )
        is_visible = post is not None
        cleanups.mongo_c2_cleanup(db, comment_id)
        return is_visible
    finally:
        db.client.close()


def run_c2(database):
    test_func = pg_c2_once if database == "postgres" else mongo_c2_once
    correct = 0

    for i in range(CONSISTENCY_ITERATIONS):
        if test_func():
            correct += 1
        if (i + 1) % 10 == 0:
            print(f"  C2 ({database}): {i + 1}/{CONSISTENCY_ITERATIONS}")

    return correct


def main():
    print("Running consistency benchmarks...")

    print("Running C1 (postgres)...")
    correct = run_pg_c1()
    save_consistency_results("C1", "postgres", correct, CONSISTENCY_ITERATIONS)

    print("Running C1 (mongodb)...")
    correct = run_mongo_c1()
    save_consistency_results("C1", "mongodb", correct, CONSISTENCY_ITERATIONS)

    for db_name in ["postgres", "mongodb"]:
        print(f"Running C2 ({db_name})...")
        correct = run_c2(db_name)
        save_consistency_results("C2", db_name, correct, CONSISTENCY_ITERATIONS)


if __name__ == "__main__":
    main()
