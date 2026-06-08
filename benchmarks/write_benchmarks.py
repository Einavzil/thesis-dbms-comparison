from datetime import datetime, timezone
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_pg_connection, get_mongo_database, ITERATIONS, WARMUP, USER_ID, POST_ID
from utils import measure_with_cleanup, save_results
import cleanups

# W1: Insert a new comment on a post
PG_W1 = """
    INSERT INTO comments (postId, userId, score, text, creationDate)
    VALUES (%s, %s, 0, %s, %s)
    RETURNING id;
    """

# update the comment count in comments table
PG_W1_UPDATE_COMMENT_COUNT = """
    UPDATE posts
    SET commentCount = COALESCE(commentCount, 0) + 1
    WHERE id = %s;
    """

def pg_w1(conn):
    with conn.cursor() as cur:
        cur.execute(PG_W1, (POST_ID, USER_ID, "W1 test comment", datetime.now(timezone.utc).replace(tzinfo=None)))
        comment_id = cur.fetchone()[0]
        cur.execute(PG_W1_UPDATE_COMMENT_COUNT, (POST_ID,))
        conn.commit()
    return comment_id

# W2: Insert a new post
PG_W2 = """
    INSERT INTO posts (postTypeId, ownerUserId, score, title, body, creationDate)
    VALUES (%s, %s, 0, %s, %s, %s)
    RETURNING id;
    """
def pg_w2(conn):
    with conn.cursor() as cur:
        cur.execute(PG_W2, (1, USER_ID, "W2 test post", "This is the body of the W2 test post", datetime.now(timezone.utc).replace(tzinfo=None)))
        post_id = cur.fetchone()[0]
        conn.commit()
    return post_id

# W3: Update post score after vote
PG_W3 = """
    UPDATE posts
    SET score = score + 1
    WHERE id = %s;
    """
def pg_w3(conn):  
    with conn.cursor() as cur:
        cur.execute(PG_W3, (POST_ID,))
        conn.commit()

# W4: update user reputation after vote
PG_W4 = """
    UPDATE users
    SET reputation = reputation + %s
    WHERE id = %s;
    """
def pg_w4(conn):
    with conn.cursor() as cur:
        cur.execute(PG_W4, (10, USER_ID))  # increase reputation by 10 for an upvote
        conn.commit()

# W1: Insert a new comment on a post and update comment count
def mongo_w1(db):
    comment_id = get_next_sequence(db, "commentId")
    db.posts.update_one(
        { "_id": POST_ID },
        { "$push": { "comments": {
            "id": comment_id,
            "userId": USER_ID,
            "score": 0,
            "text": "W1 test comment",
            "creationDate": datetime.now(timezone.utc).replace(tzinfo=None)
        }},
        "$inc": { "commentCount": 1 }
        }
    )
    return comment_id

# W2: Insert a new post
def mongo_w2(db):
    post_id = get_next_sequence(db, "postId")
    db.posts.insert_one({
        "_id": post_id,
        "postTypeId": 1,
        "ownerUserId": USER_ID,
        "score": 0,
        "title": "W2 test post",
        "body": "This is the body of the W2 test post",
        "creationDate": datetime.now(timezone.utc).replace(tzinfo=None),
        "commentCount": 0,
        "comments": []
    })
    return post_id

# W3: Update post score after vote
def mongo_w3(db):
    db.posts.update_one(
        { "_id": POST_ID },
        { "$inc": { "score": 1 } }
    )

# W4: update user reputation after vote
def mongo_w4(db):
    db.users.update_one(
        { "_id": USER_ID },
        { "$inc": { "reputation": 10 } }
    )

# get next IDs for comments and posts in mongo
def get_next_sequence(db, name):
    result = db.counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        return_document=True
    )
    return result["seq"]

def main():
    # PostgreSQL connection and benchmarks
    conn = get_pg_connection()
    try:
        for op_name, op_func, cleanup_func in [
            ("W1", lambda: pg_w1(conn), lambda data: cleanups.pg_w1_cleanup(conn, data)),  
            ("W2", lambda: pg_w2(conn), lambda data: cleanups.pg_w2_cleanup(conn, data)),
            ("W3", lambda: pg_w3(conn), lambda data: cleanups.pg_w3_cleanup(conn)),
            ("W4", lambda: pg_w4(conn), lambda data: cleanups.pg_w4_cleanup(conn)),
        ]:
            times = measure_with_cleanup(op_func, cleanup_func, ITERATIONS, WARMUP)
            save_results(op_name, "postgres", times)
    finally:
        conn.close()

    # MongoDB connection and benchmarks
    mongo_db = get_mongo_database()
    for op_name, op_func, cleanup_func in [
        ("W1", lambda: mongo_w1(mongo_db), lambda data: cleanups.mongo_w1_cleanup(mongo_db, data)),  
        ("W2", lambda: mongo_w2(mongo_db), lambda data: cleanups.mongo_w2_cleanup(mongo_db, data)),
        ("W3", lambda: mongo_w3(mongo_db), lambda data: cleanups.mongo_w3_cleanup(mongo_db)),
        ("W4", lambda: mongo_w4(mongo_db), lambda data: cleanups.mongo_w4_cleanup(mongo_db)),
    ]:
        times = measure_with_cleanup(op_func, cleanup_func, ITERATIONS, WARMUP)
        save_results(op_name, "mongodb", times)
    mongo_db.client.close()

if __name__ == "__main__":
    main()
