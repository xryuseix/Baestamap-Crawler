from google.cloud import firestore
from get_location import url2Location
import requests
import datetime
import json


def getOldTags(fs, max: int):
    hashTags_ref = fs.db.collection("hashTag")
    query = hashTags_ref.order_by(
        "timestamp", direction=firestore.Query.ASCENDING
    ).limit(max)
    return query.get()


def uploadPosts(fs, cl, posts: list, tag_docs_id: str):
    for post in posts:
        if "permalink" not in post or post["permalink"] == "":
            print(f"error: permalink is not found: {e}")
        permalink = post["permalink"]

        location = url2Location(cl, permalink)
        try:
            doc_ref = fs.db.collection("posts").document(permalink)
            if location is None:
                continue
            doc_ref.set(
                {
                    "hashTagDocsId": tag_docs_id,
                    "location": location,
                    "permalink": permalink,
                    "timestamp": datetime.datetime.now(tz=datetime.timezone.utc),
                }
            )
        except Exception as e:
            print(f"error: {e}")
            continue


def deleteHashTag(fs, tag_docs_id: str):
    tag_ref = fs.db.collection("hashTag").document(tag_docs_id)
    tag_ref.delete()


# serch_type: top_media or recent_media
def getPostsFromAPI(fs, cl, credentials: dict, serch_type: str = "recent_media"):
    old_tags = getOldTags(fs=fs, max=50)
    INSTAGRAM_ID = credentials["instagram_id"]
    ACCESS_TOKEN = credentials["access_token"]

    fields = [
        "id",
        "permalink",
        "timestamp",
    ]
    fields_str = ",".join(fields)
    limit = 100

    for hashtag in old_tags:
        print("info: collect posts from hashtag:", hashtag.get("hashTag"))
        tag_docs_id = hashtag.id
        hashtag = hashtag.to_dict()
        if "hashTagId" not in hashtag:
            print(f"error: not found hashTagId in {hashtag}")
            continue
        hashtag_id = hashtag["hashTagId"]
        print(hashtag_id)

        url = f"https://graph.facebook.com/{hashtag_id}/{serch_type}?user_id={INSTAGRAM_ID}&access_token={ACCESS_TOKEN}&fields={fields_str}&limit={limit}"
        response = requests.get(url)

        try:
            json_data = response.json()
        except json.decoder.JSONDecodeError:
            print("error: json decode error")
            continue

        posts = []
        try:
            for post_data in json_data["data"]:
                post = {
                    "permalink": post_data["permalink"].rstrip("/").split("/")[-1],
                    "timestamp": post_data["timestamp"],
                }
                posts.append(post)
        except KeyError as e:
            print(f'error: {e}. (In collect posts from hashtag: {hashtag["hashTag"]})')
            continue
        except Exception as e:
            print(f"error: {e}")
            continue
        uploadPosts(fs=fs, cl=cl, posts=posts, tag_docs_id=tag_docs_id)
        if len(posts) == 0:
            print(f"info: delete HashTag Docs {tag_docs_id}: {hashtag.get('hashTag')}")
            deleteHashTag(fs=fs, tag_docs_id=tag_docs_id)
    return posts


# serch_type: top_media or recent_media
def getPostsFromLibrary(fs, cl):
    old_tags = getOldTags(fs=fs, max=50)

    for hashtag in old_tags:
        print("info: collect posts from hashtag:", hashtag.get("hashTag"))
        tag_docs_id = hashtag.id
        hashtag = hashtag.to_dict()
        if "hashTagId" not in hashtag:
            print(f"error: not found hashTagId in {hashtag}")
            continue
        hashtag_id = hashtag["hashTagId"]
        print(hashtag_id)

        # TODO: いずれrecentにする
        res = cl.hashtag_medias_top(hashtag["hashTag"], amount=100)
        posts = []
        try:
            for post_data in res:
                post = {
                    "permalink": post_data.dict()["code"],
                    "timestamp": post_data.dict()["taken_at"],
                }
                posts.append(post)
        except KeyError as e:
            print(f'error: {e}. (In collect posts from hashtag: {hashtag["hashTag"]})')
            continue
        except Exception as e:
            print(f"error: {e}")
            continue
        uploadPosts(fs=fs, cl=cl, posts=posts, tag_docs_id=tag_docs_id)
        fs.db.collection("hashTag").document(tag_docs_id).update(
            {"timestamp": datetime.datetime.now(tz=datetime.timezone.utc)}
        )
        if len(posts) == 0:
            print(f"info: delete HashTag Docs {tag_docs_id}: {hashtag.get('hashTag')}")
            deleteHashTag(fs=fs, tag_docs_id=tag_docs_id)
    return posts
