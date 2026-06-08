"""Initialize the PostgreSQL database for the DBMS comparison project.

Creates all tables from db-schema-design.md and loads the XML seed data.
FK constraints are omitted: the dataset references deleted users/posts not
present in the XML exports.
"""

import os
import xml.etree.ElementTree as ET
import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {
    "dbname": "stackoverflow",
    "user": "thesis",
    "password": "thesis",
    "host": "localhost",
    "port": "5432",
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "../../datadump-project")

BATCH_SIZE = 5000

CREATE_SQL = """
DROP TABLE IF EXISTS post_tags;
DROP TABLE IF EXISTS post_history;
DROP TABLE IF EXISTS post_links;
DROP TABLE IF EXISTS badges;
DROP TABLE IF EXISTS votes;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    Id              INT PRIMARY KEY,
    Reputation      INT,
    DisplayName     VARCHAR(255),
    CreationDate    TIMESTAMP,
    LastAccessDate  TIMESTAMP,
    WebsiteUrl      VARCHAR(512),
    Location        VARCHAR(255),
    AboutMe         TEXT,
    Views           INT,
    UpVotes         INT,
    DownVotes       INT,
    AccountId       INT
);

CREATE TABLE posts (
    Id                    INT PRIMARY KEY,
    PostTypeId            SMALLINT,
    ParentId              INT,
    AcceptedAnswerId      INT,
    CreationDate          TIMESTAMP,
    Score                 INT,
    ViewCount             INT,
    Body                  TEXT,
    Title                 VARCHAR(512),
    OwnerUserId           INT,
    OwnerDisplayName      VARCHAR(255),
    LastEditorUserId      INT,
    LastEditorDisplayName VARCHAR(255),
    LastEditDate          TIMESTAMP,
    LastActivityDate      TIMESTAMP,
    AnswerCount           INT,
    CommentCount          INT,
    ClosedDate            TIMESTAMP,
    CommunityOwnedDate    TIMESTAMP,
    ContentLicense        VARCHAR(50)
);

CREATE TABLE tags (
    Id            INT PRIMARY KEY,
    TagName       VARCHAR(100),
    Count         INT,
    ExcerptPostId INT,
    WikiPostId    INT
);

CREATE TABLE post_tags (
    PostId INT,
    TagId  INT,
    PRIMARY KEY (PostId, TagId)
);

CREATE TABLE comments (
    Id              INT PRIMARY KEY,
    PostId          INT,
    Score           INT,
    Text            TEXT,
    CreationDate    TIMESTAMP,
    UserId          INT,
    UserDisplayName VARCHAR(255)
);

CREATE TABLE votes (
    Id            INT PRIMARY KEY,
    PostId        INT,
    VoteTypeId    SMALLINT,
    UserId        INT,
    CreationDate  TIMESTAMP,
    BountyAmount  INT
);

CREATE TABLE post_history (
    Id                   INT PRIMARY KEY,
    PostHistoryTypeId    SMALLINT,
    PostId               INT,
    RevisionGUID         VARCHAR(36),
    CreationDate         TIMESTAMP,
    UserId               INT,
    UserDisplayName      VARCHAR(255),
    Text                 TEXT,
    Comment              TEXT,
    ContentLicense       VARCHAR(50)
);

CREATE TABLE badges (
    Id       INT PRIMARY KEY,
    UserId   INT,
    Name     VARCHAR(100),
    Date     TIMESTAMP,
    Class    SMALLINT,
    TagBased BOOLEAN
);

CREATE TABLE post_links (
    Id            INT PRIMARY KEY,
    CreationDate  TIMESTAMP,
    PostId        INT,
    RelatedPostId INT,
    LinkTypeId    SMALLINT
);
"""

# Indexes are created after all data is loaded — much faster than
# maintaining them incrementally during bulk inserts.
INDEX_SQL = """
CREATE INDEX ON posts (PostTypeId);
CREATE INDEX ON posts (ParentId);
CREATE INDEX ON posts (OwnerUserId);
CREATE INDEX ON posts (PostTypeId, Score DESC, Id ASC);
CREATE INDEX ON comments (PostId);
CREATE INDEX ON comments (UserId);
CREATE INDEX ON votes (PostId);
CREATE INDEX ON votes (UserId);
CREATE INDEX ON votes (VoteTypeId);
CREATE INDEX ON badges (UserId);
CREATE INDEX ON post_history (PostId);
"""


def safe_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def safe_str(value, max_len=None):
    if value is None:
        return None
    s = str(value)
    return s[:max_len] if max_len else s


def safe_bool(value):
    if value is None:
        return None
    return value.strip().lower() == "true"


def parse_tags(tag_str):
    if not tag_str:
        return []
    return [t for t in tag_str.strip("|").split("|") if t]


def iter_xml(filepath):
    """Stream <row> elements one at a time — avoids loading the full file into RAM."""
    context = ET.iterparse(filepath, events=("start", "end"))
    _, root = next(context)
    for event, elem in context:
        if event == "end" and elem.tag == "row":
            yield elem.attrib
            root.clear()


def load_users(cur, filepath):
    sql = """INSERT INTO users (Id, Reputation, DisplayName, CreationDate, LastAccessDate,
                                WebsiteUrl, Location, AboutMe, Views, UpVotes, DownVotes, AccountId)
             VALUES %s ON CONFLICT (Id) DO NOTHING"""
    batch, total = [], 0
    for r in iter_xml(filepath):
        batch.append((
            safe_int(r.get("Id")),
            safe_int(r.get("Reputation")),
            safe_str(r.get("DisplayName"), 255),
            r.get("CreationDate"),
            r.get("LastAccessDate"),
            safe_str(r.get("WebsiteUrl"), 512),
            safe_str(r.get("Location"), 255),
            r.get("AboutMe"),
            safe_int(r.get("Views")),
            safe_int(r.get("UpVotes")),
            safe_int(r.get("DownVotes")),
            safe_int(r.get("AccountId")),
        ))
        if len(batch) >= BATCH_SIZE:
            execute_values(cur, sql, batch)
            total += len(batch)
            batch = []
    if batch:
        execute_values(cur, sql, batch)
        total += len(batch)
    return total


def load_tags(cur, filepath):
    sql = """INSERT INTO tags (Id, TagName, Count, ExcerptPostId, WikiPostId)
             VALUES %s ON CONFLICT (Id) DO NOTHING"""
    batch, total = [], 0
    tag_name_to_id = {}
    for r in iter_xml(filepath):
        tag_id = safe_int(r.get("Id"))
        tag_name = safe_str(r.get("TagName"), 100)
        if tag_name and tag_id:
            tag_name_to_id[tag_name] = tag_id
        batch.append((tag_id, tag_name, safe_int(r.get("Count")),
                      safe_int(r.get("ExcerptPostId")), safe_int(r.get("WikiPostId"))))
        if len(batch) >= BATCH_SIZE:
            execute_values(cur, sql, batch)
            total += len(batch)
            batch = []
    if batch:
        execute_values(cur, sql, batch)
        total += len(batch)
    return total, tag_name_to_id


def load_posts(cur, filepath, tag_name_to_id):
    post_sql = """INSERT INTO posts (Id, PostTypeId, ParentId, AcceptedAnswerId, CreationDate,
                                     Score, ViewCount, Body, Title, OwnerUserId, OwnerDisplayName,
                                     LastEditorUserId, LastEditorDisplayName, LastEditDate,
                                     LastActivityDate, AnswerCount, CommentCount, ClosedDate,
                                     CommunityOwnedDate, ContentLicense)
                  VALUES %s ON CONFLICT (Id) DO NOTHING"""
    tag_sql = "INSERT INTO post_tags (PostId, TagId) VALUES %s ON CONFLICT DO NOTHING"
    post_batch, tag_batch, total = [], [], 0
    for r in iter_xml(filepath):
        post_id = safe_int(r.get("Id"))
        post_batch.append((
            post_id,
            safe_int(r.get("PostTypeId")),
            safe_int(r.get("ParentId")),
            safe_int(r.get("AcceptedAnswerId")),
            r.get("CreationDate"),
            safe_int(r.get("Score")),
            safe_int(r.get("ViewCount")),
            r.get("Body"),
            safe_str(r.get("Title"), 512),
            safe_int(r.get("OwnerUserId")),
            safe_str(r.get("OwnerDisplayName"), 255),
            safe_int(r.get("LastEditorUserId")),
            safe_str(r.get("LastEditorDisplayName"), 255),
            r.get("LastEditDate"),
            r.get("LastActivityDate"),
            safe_int(r.get("AnswerCount")),
            safe_int(r.get("CommentCount")),
            r.get("ClosedDate"),
            r.get("CommunityOwnedDate"),
            safe_str(r.get("ContentLicense"), 50),
        ))
        for tag_name in parse_tags(r.get("Tags")):
            tag_id = tag_name_to_id.get(tag_name)
            if tag_id is not None:
                tag_batch.append((post_id, tag_id))
        if len(post_batch) >= BATCH_SIZE:
            execute_values(cur, post_sql, post_batch)
            if tag_batch:
                execute_values(cur, tag_sql, tag_batch)
            total += len(post_batch)
            post_batch, tag_batch = [], []
    if post_batch:
        execute_values(cur, post_sql, post_batch)
        if tag_batch:
            execute_values(cur, tag_sql, tag_batch)
        total += len(post_batch)
    return total


def load_comments(cur, filepath):
    sql = """INSERT INTO comments (Id, PostId, Score, Text, CreationDate, UserId, UserDisplayName)
             VALUES %s ON CONFLICT (Id) DO NOTHING"""
    batch, total = [], 0
    for r in iter_xml(filepath):
        batch.append((
            safe_int(r.get("Id")),
            safe_int(r.get("PostId")),
            safe_int(r.get("Score")),
            r.get("Text") or "",
            r.get("CreationDate"),
            safe_int(r.get("UserId")),
            safe_str(r.get("UserDisplayName"), 255),
        ))
        if len(batch) >= BATCH_SIZE:
            execute_values(cur, sql, batch)
            total += len(batch)
            batch = []
    if batch:
        execute_values(cur, sql, batch)
        total += len(batch)
    return total


def load_votes(cur, filepath):
    sql = """INSERT INTO votes (Id, PostId, VoteTypeId, UserId, CreationDate, BountyAmount)
             VALUES %s ON CONFLICT (Id) DO NOTHING"""
    batch, total = [], 0
    for r in iter_xml(filepath):
        batch.append((
            safe_int(r.get("Id")),
            safe_int(r.get("PostId")),
            safe_int(r.get("VoteTypeId")),
            safe_int(r.get("UserId")),
            r.get("CreationDate"),
            safe_int(r.get("BountyAmount")),
        ))
        if len(batch) >= BATCH_SIZE:
            execute_values(cur, sql, batch)
            total += len(batch)
            batch = []
    if batch:
        execute_values(cur, sql, batch)
        total += len(batch)
    return total


def load_badges(cur, filepath):
    sql = """INSERT INTO badges (Id, UserId, Name, Date, Class, TagBased)
             VALUES %s ON CONFLICT (Id) DO NOTHING"""
    batch, total = [], 0
    for r in iter_xml(filepath):
        batch.append((
            safe_int(r.get("Id")),
            safe_int(r.get("UserId")),
            safe_str(r.get("Name"), 100),
            r.get("Date"),
            safe_int(r.get("Class")),
            safe_bool(r.get("TagBased")),
        ))
        if len(batch) >= BATCH_SIZE:
            execute_values(cur, sql, batch)
            total += len(batch)
            batch = []
    if batch:
        execute_values(cur, sql, batch)
        total += len(batch)
    return total


def load_post_links(cur, filepath):
    sql = """INSERT INTO post_links (Id, CreationDate, PostId, RelatedPostId, LinkTypeId)
             VALUES %s ON CONFLICT (Id) DO NOTHING"""
    batch, total = [], 0
    for r in iter_xml(filepath):
        batch.append((
            safe_int(r.get("Id")),
            r.get("CreationDate"),
            safe_int(r.get("PostId")),
            safe_int(r.get("RelatedPostId")),
            safe_int(r.get("LinkTypeId")),
        ))
        if len(batch) >= BATCH_SIZE:
            execute_values(cur, sql, batch)
            total += len(batch)
            batch = []
    if batch:
        execute_values(cur, sql, batch)
        total += len(batch)
    return total


def load_post_history(cur, filepath):
    sql = """INSERT INTO post_history (Id, PostHistoryTypeId, PostId, RevisionGUID,
                                       CreationDate, UserId, UserDisplayName, Text,
                                       Comment, ContentLicense)
             VALUES %s ON CONFLICT (Id) DO NOTHING"""
    batch, total = [], 0
    for r in iter_xml(filepath):
        batch.append((
            safe_int(r.get("Id")),
            safe_int(r.get("PostHistoryTypeId")),
            safe_int(r.get("PostId")),
            safe_str(r.get("RevisionGUID"), 36),
            r.get("CreationDate"),
            safe_int(r.get("UserId")),
            safe_str(r.get("UserDisplayName"), 255),
            r.get("Text"),
            r.get("Comment"),
            safe_str(r.get("ContentLicense"), 50),
        ))
        if len(batch) >= BATCH_SIZE:
            execute_values(cur, sql, batch)
            total += len(batch)
            batch = []
    if batch:
        execute_values(cur, sql, batch)
        total += len(batch)
    return total

def setup_id_sequence(cur):
    # configure auto-incrementing IDs for benchmark write operations

    cur.execute(f"CREATE SEQUENCE IF NOT EXISTS comment_id_seq")
    cur.execute(f"CREATE SEQUENCE IF NOT EXISTS post_id_seq")

    cur.execute("ALTER TABLE comments ALTER COLUMN Id SET DEFAULT nextval(comment_id_seq')")
    cur.execute("ALTER TABLE posts ALTER COLUMN Id SET DEFAULT nextval('post_id_seq')")

    cur.execute("SELECT COALESCE(MAX(Id), 0) FROM comments")
    max_comment_id = cur.fetchone()[0]
    cur.execute("SELECT COALESCE(MAX(Id), 0) FROM posts")
    max_post_id = cur.fetchone()[0]

    cur.execute("SELECT setval('comment_id_seq, %s, true')", (max_comment_id,))
    cur.execute("SELECT setval('post_id_seq, %s, true')", (max_post_id,))

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    def p(filename):
        return os.path.join(DATA_DIR, filename)

    try:
        print("Creating schema...")
        cur.execute(CREATE_SQL)
        conn.commit()

        print("Loading Users.xml...")
        n = load_users(cur, p("Users.xml"))
        conn.commit()
        print(f"  {n} rows.")

        print("Loading Tags.xml...")
        n, tag_name_to_id = load_tags(cur, p("Tags.xml"))
        conn.commit()
        print(f"  {n} rows.")

        print("Loading Posts.xml...")
        n = load_posts(cur, p("Posts.xml"), tag_name_to_id)
        conn.commit()
        print(f"  {n} rows.")

        print("Loading Comments.xml...")
        n = load_comments(cur, p("Comments.xml"))
        conn.commit()
        print(f"  {n} rows.")

        print("Loading Votes.xml...")
        n = load_votes(cur, p("Votes.xml"))
        conn.commit()
        print(f"  {n} rows.")

        print("Loading Badges.xml...")
        n = load_badges(cur, p("Badges.xml"))
        conn.commit()
        print(f"  {n} rows.")

        print("Loading PostLinks.xml...")
        n = load_post_links(cur, p("PostLinks.xml"))
        conn.commit()
        print(f"  {n} rows.")

        print("Loading PostHistory.xml...")
        n = load_post_history(cur, p("PostHistory.xml"))
        conn.commit()
        print(f"  {n} rows.")

        print("Creating indexes...")
        cur.execute(INDEX_SQL)
        conn.commit()

        print("Configuring ID sequences...")
        setup_id_sequence(cur)
        conn.commit()

        print("Done.")
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
