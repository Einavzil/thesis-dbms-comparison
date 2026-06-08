""" Read Benchmarks: R1, R2, R3, R4."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_pg_connection, get_mongo_database, ITERATIONS, WARMUP, USER_ID, POST_ID
from utils import measure, save_results

# R1: retrieve user profile and last 20 posts
PG_R1 = """
    SELECT u.id, u.displayName, u.reputation, p.id, p.title, p.score, p.creationDate
    FROM users u
    JOIN posts p ON p.ownerUserId = u.id
    WHERE u.id = %s
    ORDER BY p.creationDate DESC
    LIMIT 20;
    """

def pg_r1(conn):
    with conn.cursor() as cur:
        cur.execute(PG_R1, (USER_ID,))
        return cur.fetchall()

# R2: retrieve post with all comments
PG_R2 = """
    SELECT p.id, p.title, p.body, p.score, c.creationDate, c.text, c.score
    FROM posts p
    LEFT JOIN comments c ON c.postId = p.id
    WHERE p.id = %s;
    """

def pg_r2(conn):
    with conn.cursor() as cur:
        cur.execute(PG_R2, (POST_ID,))
        return cur.fetchall()

# R3: retrieve top 10 posts by score
PG_R3 = """
    SELECT id, title, score, viewCount
    FROM posts
    WHERE postTypeId = 1
    ORDER BY score DESC, id ASC
    LIMIT 10;
    """

def pg_r3(conn):
    with conn.cursor() as cur:
        cur.execute(PG_R3)
        return cur.fetchall()

# R4: count comments per post for 10 posts
PG_R4 = """
    SELECT p.id, p.title, COUNT(c.id) AS comment_count
    FROM posts p
    LEFT JOIN comments c ON c.postId = p.id
    WHERE p.postTypeId = 1
    GROUP BY p.id, p.title
    ORDER BY p.id
    LIMIT 10;
    """

def pg_r4(conn):
    with conn.cursor() as cur:
        cur.execute(PG_R4)
        return cur.fetchall()

# MongoDB queries 
def mongo_r1(db):
    user = db.users.find_one({ "_id": USER_ID}, { "displayName": 1, "reputation": 1 })
    posts = list(db.posts.find(
        { "ownerUserId": USER_ID },
        { "title": 1, "score": 1, "creationDate": 1 }
    ).sort([("creationDate", -1)]).limit(20))
    return user, posts

def mongo_r2(db):
    return db.posts.find_one({ "_id": POST_ID}, { "title": 1, "body": 1, "score": 1, "comments": 1 })

def mongo_r3(db):
    return list(db.posts.find(
        { "postTypeId": 1 },
        { "title": 1, "score": 1, "viewCount": 1 }
    ).sort([("score", -1), ("_id", 1)]).limit(10))

def mongo_r4(db):
    pipeline = [
    { "$match": { "postTypeId": 1 } },
{ "$sort": { "_id": 1 } },
    { "$limit": 10 },
    { "$project": {
        "title": 1,
        "commentCount": { "$size": { "$ifNull": ["$comments", []] } } } }
    ]
    return list(db.posts.aggregate(pipeline))

def main():
    # postgreSQL connection and benchmarks
    conn = get_pg_connection()
    try:
        for op_name, op_func in [
            ("R1", lambda: pg_r1(conn)),  
            ("R2", lambda: pg_r2(conn)), 
            ("R3", lambda: pg_r3(conn)),
            ("R4", lambda: pg_r4(conn)),
        ]:
            times = measure(op_func, ITERATIONS, WARMUP)
            save_results(op_name, "postgres", times)
    finally:
        conn.close()

    # MongoDB connection and benchmarks
    mongo_db = get_mongo_database()
    for op_name, op_func in [
        ("R1", lambda: mongo_r1(mongo_db)),  
        ("R2", lambda: mongo_r2(mongo_db)), 
        ("R3", lambda: mongo_r3(mongo_db)),
        ("R4", lambda: mongo_r4(mongo_db)),
    ]:
        times = measure(op_func, ITERATIONS, WARMUP)
        save_results(op_name, "mongodb", times)
    mongo_db.client.close()

if __name__ == "__main__":
    main()
