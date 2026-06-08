"""Initialize the MongoDB database for the DBMS comparison project.

Creates all collections from db-schema-design.md and loads the XML seed data.

Embedding decisions (per schema design):
  - comments  → embedded array inside posts
  - badges    → embedded array inside users
  - tags      → stored as string arrays inside posts (no bridge collection)
  - votes, post_history, post_links, tags → separate collections
"""

import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from pymongo import MongoClient, ASCENDING

MONGO_URI = "mongodb://thesis:thesis@localhost:27017/stackoverflow?authSource=admin"
DB_NAME = "stackoverflow"

DATA_DIR = os.path.join(os.path.dirname(__file__), "../../datadump-project")

BATCH_SIZE = 2000


def iter_xml(filepath):
    """Stream <row> elements one at a time — avoids loading the full file into RAM."""
    context = ET.iterparse(filepath, events=("start", "end"))
    _, root = next(context)
    for event, elem in context:
        if event == "end" and elem.tag == "row":
            yield elem.attrib
            root.clear()


def safe_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_tags(tag_str):
    if not tag_str:
        return []
    return [t for t in tag_str.strip("|").split("|") if t]


def insert_batched(collection, doc_iter):
    """Insert documents from an iterator in batches. Returns total count."""
    batch, total = [], 0
    for doc in doc_iter:
        batch.append(doc)
        if len(batch) >= BATCH_SIZE:
            collection.insert_many(batch, ordered=False)
            total += len(batch)
            batch = []
    if batch:
        collection.insert_many(batch, ordered=False)
        total += len(batch)
    return total


# ---------------------------------------------------------------------------
# Step 1: build in-memory lookup dicts for embedded data (streamed, not bulk)
# ---------------------------------------------------------------------------

def build_badges_lookup(filepath):
    """Stream Badges.xml → dict[userId → list of badge dicts]."""
    print("  Reading Badges.xml for embedding...")
    badges_by_user = defaultdict(list)
    for r in iter_xml(filepath):
        uid = safe_int(r.get("UserId"))
        if uid is None:
            continue
        badges_by_user[uid].append({
            "id":       safe_int(r.get("Id")),
            "name":     r.get("Name"),
            "date":     r.get("Date"),
            "class":    safe_int(r.get("Class")),
            "tagBased": r.get("TagBased", "").strip().lower() == "true",
        })
    print(f"  {sum(len(v) for v in badges_by_user.values())} badges across {len(badges_by_user)} users.")
    return badges_by_user


def build_comments_lookup(filepath):
    """Stream Comments.xml → dict[postId → list of comment dicts]."""
    print("  Reading Comments.xml for embedding...")
    comments_by_post = defaultdict(list)
    for r in iter_xml(filepath):
        pid = safe_int(r.get("PostId"))
        if pid is None:
            continue
        comments_by_post[pid].append({
            "id":              safe_int(r.get("Id")),
            "score":           safe_int(r.get("Score")),
            "text":            r.get("Text"),
            "creationDate":    r.get("CreationDate"),
            "userId":          safe_int(r.get("UserId")),
            "userDisplayName": r.get("UserDisplayName"),
        })
    print(f"  {sum(len(v) for v in comments_by_post.values())} comments across {len(comments_by_post)} posts.")
    return comments_by_post


# ---------------------------------------------------------------------------
# Step 2: stream each XML file and yield MongoDB documents
# ---------------------------------------------------------------------------

def users_docs(filepath, badges_by_user):
    for r in iter_xml(filepath):
        uid = safe_int(r.get("Id"))
        yield {
            "_id":            uid,
            "displayName":    r.get("DisplayName"),
            "reputation":     safe_int(r.get("Reputation")),
            "creationDate":   r.get("CreationDate"),
            "lastAccessDate": r.get("LastAccessDate"),
            "websiteUrl":     r.get("WebsiteUrl"),
            "location":       r.get("Location"),
            "aboutMe":        r.get("AboutMe"),
            "views":          safe_int(r.get("Views")),
            "upVotes":        safe_int(r.get("UpVotes")),
            "downVotes":      safe_int(r.get("DownVotes")),
            "accountId":      safe_int(r.get("AccountId")),
            "badges":         badges_by_user.get(uid, []),
        }


def posts_docs(filepath, comments_by_post):
    for r in iter_xml(filepath):
        pid = safe_int(r.get("Id"))
        yield {
            "_id":                   pid,
            "postTypeId":            safe_int(r.get("PostTypeId")),
            "parentId":              safe_int(r.get("ParentId")),
            "acceptedAnswerId":      safe_int(r.get("AcceptedAnswerId")),
            "creationDate":          r.get("CreationDate"),
            "score":                 safe_int(r.get("Score")),
            "viewCount":             safe_int(r.get("ViewCount")),
            "body":                  r.get("Body"),
            "title":                 r.get("Title"),
            "ownerUserId":           safe_int(r.get("OwnerUserId")),
            "ownerDisplayName":      r.get("OwnerDisplayName"),
            "lastEditorUserId":      safe_int(r.get("LastEditorUserId")),
            "lastEditorDisplayName": r.get("LastEditorDisplayName"),
            "lastEditDate":          r.get("LastEditDate"),
            "lastActivityDate":      r.get("LastActivityDate"),
            "answerCount":           safe_int(r.get("AnswerCount")),
            "commentCount":          safe_int(r.get("CommentCount")),
            "closedDate":            r.get("ClosedDate"),
            "communityOwnedDate":    r.get("CommunityOwnedDate"),
            "contentLicense":        r.get("ContentLicense"),
            "tags":                  parse_tags(r.get("Tags")),
            "comments":              comments_by_post.get(pid, []),
        }


def votes_docs(filepath):
    for r in iter_xml(filepath):
        yield {
            "_id":          safe_int(r.get("Id")),
            "postId":       safe_int(r.get("PostId")),
            "voteTypeId":   safe_int(r.get("VoteTypeId")),
            "userId":       safe_int(r.get("UserId")),
            "creationDate": r.get("CreationDate"),
            "bountyAmount": safe_int(r.get("BountyAmount")),
        }


def post_history_docs(filepath):
    for r in iter_xml(filepath):
        yield {
            "_id":               safe_int(r.get("Id")),
            "postId":            safe_int(r.get("PostId")),
            "postHistoryTypeId": safe_int(r.get("PostHistoryTypeId")),
            "revisionGUID":      r.get("RevisionGUID"),
            "creationDate":      r.get("CreationDate"),
            "userId":            safe_int(r.get("UserId")),
            "userDisplayName":   r.get("UserDisplayName"),
            "text":              r.get("Text"),
            "comment":           r.get("Comment"),
            "contentLicense":    r.get("ContentLicense"),
        }


def post_links_docs(filepath):
    for r in iter_xml(filepath):
        yield {
            "_id":           safe_int(r.get("Id")),
            "postId":        safe_int(r.get("PostId")),
            "relatedPostId": safe_int(r.get("RelatedPostId")),
            "linkTypeId":    safe_int(r.get("LinkTypeId")),
            "creationDate":  r.get("CreationDate"),
        }


def tags_docs(filepath):
    for r in iter_xml(filepath):
        yield {
            "_id":           safe_int(r.get("Id")),
            "tagName":       r.get("TagName"),
            "count":         safe_int(r.get("Count")),
            "excerptPostId": safe_int(r.get("ExcerptPostId")),
            "wikiPostId":    safe_int(r.get("WikiPostId")),
        }
        
def create_indexes(db):
    db.posts.create_index([("postTypeId", ASCENDING)])
    db.posts.create_index([("parentId", ASCENDING)])
    db.posts.create_index([("ownerUserId", ASCENDING)])
    db.posts.create_index([("postTypeId", ASCENDING), ("score", -1), ("_id", ASCENDING)])
    db.posts.create_index([("tags", ASCENDING)])
    db.votes.create_index([("postId", ASCENDING)])
    db.votes.create_index([("userId", ASCENDING)])
    db.votes.create_index([("voteTypeId", ASCENDING)])
    db.post_history.create_index([("postId", ASCENDING)])
    db.post_links.create_index([("postId", ASCENDING)])


def setup_id_counters(db):
    # set up counters for generating unique IDs in write benchmarks
    max_post = db.posts.find_one(sort=[("_id", -1)])
    max_post_id = max_post["_id"] if max_post else 0

    max_comment = list(db.posts.aggregate([
        {"$unwind": "$comments"},
        {"$group": {"_id": None, "maxCommentId": {"$max": "$comments.id"}}}
    ]))
    max_comment_id = max_comment[0]["maxCommentId"] if max_comment else 0

    db.counters.update_one({"_id": "postId"}, {"$set": {"seq": max_post_id}}, upsert=True)
    db.counters.update_one({"_id": "commentId"}, {"$set": {"seq": max_comment_id}}, upsert=True)

def main():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    print("Dropping existing collections...")
    for name in ["users", "posts", "votes", "post_history", "post_links", "tags"]:
        db[name].drop()

    def p(filename):
        return os.path.join(DATA_DIR, filename)

    # Build embedding lookups first (streamed into memory as dicts).
    print("Building embedding lookups...")
    badges_by_user   = build_badges_lookup(p("Badges.xml"))
    comments_by_post = build_comments_lookup(p("Comments.xml"))

    print("Loading users...")
    n = insert_batched(db.users, users_docs(p("Users.xml"), badges_by_user))
    print(f"  {n} documents.")
    del badges_by_user

    print("Loading posts...")
    n = insert_batched(db.posts, posts_docs(p("Posts.xml"), comments_by_post))
    print(f"  {n} documents.")
    del comments_by_post

    print("Loading votes...")
    n = insert_batched(db.votes, votes_docs(p("Votes.xml")))
    print(f"  {n} documents.")

    print("Loading post_history...")
    n = insert_batched(db.post_history, post_history_docs(p("PostHistory.xml")))
    print(f"  {n} documents.")

    print("Loading post_links...")
    n = insert_batched(db.post_links, post_links_docs(p("PostLinks.xml")))
    print(f"  {n} documents.")

    print("Loading tags...")
    n = insert_batched(db.tags, tags_docs(p("Tags.xml")))
    print(f"  {n} documents.")

    print("Creating indexes...")
    create_indexes(db)

    print("Setting up ID counters...")
    setup_id_counters(db)

    client.close()
    print("Done.")


if __name__ == "__main__":
    main()
