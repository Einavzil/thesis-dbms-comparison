from config import POST_ID, USER_ID


# cleanup for write operations in postgres
def pg_w1_cleanup(conn, comment_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM comments WHERE id = %s;", (comment_id,))
        cur.execute("UPDATE posts SET commentCount = COALESCE(commentCount, 0) - 1 WHERE id = %s;", (POST_ID,))
        conn.commit()

def pg_w2_cleanup(conn, post_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM posts WHERE id = %s;", (post_id,))
        conn.commit()

def pg_w3_cleanup(conn):
    with conn.cursor() as cur:
        cur.execute("UPDATE posts SET score = score - 1 WHERE id = %s;", (POST_ID,))
        conn.commit()

def pg_w4_cleanup(conn):
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET reputation = reputation - 10 WHERE id = %s;", (USER_ID,))
        conn.commit()

# cleanup for write operations in mongodb
def mongo_w1_cleanup(db, comment_id):
    db.posts.update_one(
        { "_id": POST_ID },
        { "$pull": { "comments": { "id": comment_id } }, "$inc": { "commentCount": -1 } }
    )

def mongo_w2_cleanup(db, post_id):
    db.posts.delete_one({ "_id": post_id })

def mongo_w3_cleanup(db):
    db.posts.update_one(
        { "_id": POST_ID },
        { "$inc": { "score": -1 } }
    )

def mongo_w4_cleanup(db):
    db.users.update_one(
        { "_id": USER_ID },
        { "$inc": { "reputation": -10 } }
    )

# cleanup for consistency operations
def pg_c2_cleanup(conn, comment_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM comments WHERE id = %s;", (comment_id,))
        cur.execute(
            """
            UPDATE posts
            SET commentCount = (
                SELECT COUNT(*)
                FROM comments
                WHERE comments.postId = posts.id
            )
            WHERE id = %s;
            """,
            (POST_ID,)
        )
        conn.commit()

def mongo_c2_cleanup(db, comment_id):
    db.posts.update_one(
        { "_id": POST_ID },
        { "$pull": { "comments": { "id": comment_id } } }
    )
    mongo_recalculate_comment_count(db)

# cleanup for scalability operations
def pg_s1_w1_cleanup(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM comments WHERE postId = %s AND text = %s;", (POST_ID, "S1 test comment"))
        cur.execute(
            """
            UPDATE posts
            SET commentCount = (
                SELECT COUNT(*)
                FROM comments
                WHERE comments.postId = posts.id
            )
            WHERE id = %s;
            """,
            (POST_ID,)
        )
        conn.commit()

def mongo_s1_w1_cleanup(db):
    db.posts.update_one(
        { "_id": POST_ID },
        { "$pull": { "comments": { "text": "S1 test comment" } } }
    )
    mongo_recalculate_comment_count(db)

def mongo_recalculate_comment_count(db):
    post = db.posts.find_one({ "_id": POST_ID }, { "comments": 1 })
    comment_count = len(post.get("comments", [])) if post else 0
    db.posts.update_one(
        { "_id": POST_ID },
        { "$set": { "commentCount": comment_count } }
    )
