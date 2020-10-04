from dotenv import load_dotenv
import os
import praw
from pprint import pprint
from toolz.curried import *
from bidi.algorithm import get_display

load_dotenv()

creds = {
    "client_id": os.environ["client_id"],
    "client_secret": os.environ["client_secret"],
    "username": os.environ["uname"],
    "password": os.environ["password"],
    "user_agent": os.environ["user_agent"],
}

reddit = praw.Reddit(**creds)

subreddit_name = "ouijew"
subreddit = reddit.subreddit(subreddit_name)
flair = lambda f: "ויג'ו אומר: " + f


def partition(pred, lst):
    true, false = [], []
    [(false, true)[pred(var)].append(var) for var in lst]
    return true, false


def is_valid(reply):
    return len(reply.body) <= 1 or reply.body[:7] == "להתראות"


def remove(reply, reason):
    print(
        "removing https://www.reddit.com/api/info?id=t1_{} : {}".format(
            reply.id, get_display(reply.body)
        )
    )


def filter_invalid(replies, to_remove=False):
    valid, invalid = partition(is_valid, replies)
    if to_remove:
        [remove(reply, "invalid reply") for reply in invalid]
    return valid


def remove_duplicates(replies):
    left = []
    for dups in groupby(lambda r: r.body)(replies).values():
        by_time = sorted(dups, key=lambda r: r.created)
        for reply in by_time[1:]:
            remove(reply, "duplicate reply")
        left.append(by_time[0])
    return left


def process_goodbye(reply):
    try:
        return process_goodbye(reply.parent()) + reply.parent().body
    except AttributeError:
        return ""


def process_post(submission):
    print(
        "\nhttps://www.reddit.com/{}\n{}".format(
            submission.id, get_display(submission.title)
        )
    )
    submission.comments.replace_more(limit=None)
    comment_queue = filter_invalid(submission.comments[:], to_remove=True)
    goodbyes = []
    while comment_queue:
        comment = comment_queue.pop(0)
        replies = comment.replies
        if comment.body[:7] == "להתראות":
            goodbyes.append(comment)
        pipe(
            replies, filter_invalid, remove_duplicates, comment_queue.extend,
        )
    if goodbyes:
        winner = sorted(goodbyes, key=lambda reply: reply.score)[-1]
        print(get_display(process_goodbye(winner).replace("#", " ")))
    else:
        print("no winner")


def test_process_post():
    process_post(do(print)(reddit.submission(id="ik3fjg")))


def check_hot():
    for submission in subreddit.hot(limit=50):
        process_post(submission)


def main():
    check_hot()


if __name__ == "__main__":
    main()
