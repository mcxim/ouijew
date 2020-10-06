from dotenv import load_dotenv
import os
import praw
from pprint import pprint
from toolz.curried import *
from bidi.algorithm import get_display

DEBUG = True

load_dotenv()

creds = {
    "client_id": os.environ["client_id"],
    "client_secret": os.environ["client_secret"],
    "username": os.environ["uname"],
    "password": os.environ["password"],
    "user_agent": os.environ["user_agent"],
}

reddit = praw.Reddit(**creds)

# Removal reason IDs
INVALID_REPLY = "15raefp55ha4t"
SELF_REPLY = "15ra9m24jua4q"
SELF_PARTICIPATION = "15ra7m8a91qzb"
DUPLICATE_REPLY = "15rab3ega9l4j"

THRESHHOLD = 3

subreddit_name = "ouijew"
subreddit = reddit.subreddit(subreddit_name)
flair = lambda f: "ויג'ו אומר: " + f
is_goodbye = lambda s: s[:7] == "להתראות"

dop = do(compose_left(do(print), type, print))


def partition(pred, lst):
    true, false = [], []
    [(false, true)[pred(var)].append(var) for var in lst]
    return true, false


def process_goodbye(reply):
    try:
        parent = reply.parent()
        return process_goodbye(parent) + parent.body
    except AttributeError:
        return ""


def is_valid(reply):
    return len(reply.body) <= 1 or is_goodbye(reply.body)


def remove(reply, reason_id):
    print(
        "removing ({}) https://www.reddit.com/api/info?id=t1_{} : {}".format(
            reason_id, reply.id, get_display(reply.body)
        )
    )
    if not DEBUG:
        reply.remove(reason_id=reason_id)


@curry
def leave_only(args, replies):
    predicate, message_id = args
    valid, invalid = partition(predicate, replies)
    [remove(reply, message_id) for reply in invalid]
    return valid


def remove_duplicates(replies):
    left = []
    for dups in groupby(lambda r: r.body)(replies).values():
        by_time = sorted(dups, key=lambda r: r.created)
        for reply in by_time[1:]:
            remove(reply, DUPLICATE_REPLY)
        left.append(by_time[0])
    return left


def process_post(submission):
    print(
        "\nhttps://www.reddit.com/{}\n{}".format(
            submission.id, get_display(submission.title)
        )
    )
    submission.comments.replace_more(limit=None)
    comment_queue = pipe(
        submission.comments[:],
        filter(lambda r: r.banned_by is None and r.author),
        leave_only((is_valid, INVALID_REPLY)),
    )
    goodbyes = []
    while comment_queue:
        comment = comment_queue.pop(0)
        replies = comment.replies
        if is_goodbye(comment.body):
            goodbyes.append(comment)
        else:
            pipe(
                replies,
                filter(lambda r: r.banned_by is None and r.author),
                filter(is_valid),
                leave_only((lambda r: comment.author != r.author, SELF_REPLY)),
                leave_only(
                    (
                        lambda r: submission.author != r.author
                        or is_goodbye(r.body),
                        SELF_PARTICIPATION,
                    )
                ),
                remove_duplicates,
                comment_queue.extend,
            )
    try:
        winner = pipe(
            goodbyes,
            filter(lambda reply: reply.score >= THRESHHOLD),
            partial(sorted, key=lambda reply: reply.score),
            lambda gs: process_goodbye(gs[-1]),
            lambda w: str.replace(w, "#", " "),
        )
        text = flair(winner)
        print(get_display(text))
        if not DEBUG:
            submission.mod.flair(text=text)
    except IndexError:
        print("no winner")


def test_process_post():
    process_post(do(print)(reddit.submission(id="iq18sm")))


def print_removal_reason_ids():
    reasons = subreddit.mod.removal_reasons
    for reason in reasons:
        print(
            "Title: {}\nText: {}\nID: {}\n\n\n".format(
                *map(get_display)([reason.title, reason.message, reason.id])
            )
        )


def check_hot():
    for submission in subreddit.hot(limit=100):
        if not submission.stickied and not submission.link_flair_text:
            process_post(submission)


def main():
    # print(reddit.submission("it9ut3").link_flair_text)
    # print(reddit.submission("j54e28").link_flair_text)
    print(reddit.comment("g4o3sqr").author)


if __name__ == "__main__":
    check_hot()
