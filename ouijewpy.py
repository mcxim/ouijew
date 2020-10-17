from dotenv import load_dotenv
import os
import praw
import prawcore
import time
from toolz.curried import *


DEBUG = False

CHECK_HOT = 30  # Number of posts checked on each iteartion

load_dotenv()

if os.environ["flip_hebrew"].lower() in {"true", "yes", "1"}:
    from bidi.algorithm import get_display
else:
    get_display = identity

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

THRESHHOLD = 2  # Minimum "goodbye" score to get into a flair

subreddit_name = "ouijew"
subreddit = reddit.subreddit(subreddit_name)
flair = lambda f: "ויג'ו אומר: " + f
is_goodbye = lambda s: s[:7] == "להתראות"


def partition(pred, lst):
    """
    Takes a predicate and a list and returns the pair of lists of elements
    which do and do not satisfy the predicate, respectively.
    """
    true, false = [], []
    [(false, true)[pred(var)].append(var) for var in lst]
    return true, false


def process_goodbye(reply):
    """
    Traverses the comment tree starting at a "goodbye" up until the root,
    collecting the letters and returning ouija's answer.
    """
    try:
        parent = reply.parent()
        return process_goodbye(parent) + parent.body
    except AttributeError:
        return ""


def is_valid(reply):
    """
    Checks if reply's content is valid.
    """
    return len(reply.body) <= 1 or is_goodbye(reply.body)


def remove(reply, reason_id):
    """
    Removes a comment / reply as moderator, providing the given reason.
    """
    print(
        "removing ({}) https://www.reddit.com/api/info?id=t1_{} : {}".format(
            reason_id, reply.id, get_display(reply.body)
        )
    )
    if not DEBUG:
        reply.mod.remove(reason_id=reason_id)


@curry
def leave_only(args, replies):
    """
    Filters out the comments / replies that fail the predicate, remove
    the others as mod.
    """
    predicate, message_id = args
    valid, invalid = partition(predicate, replies)
    [remove(reply, message_id) for reply in invalid]
    return valid


def remove_duplicates(replies):
    """
    Detect duplicate answers, leave only the originals, remove copycats.
    """
    return pipe(
        replies,
        groupby(lambda r: r.body),
        dict.values,
        map(
            compose_left(
                partial(sorted, key=lambda r: r.created),
                lambda rs: (
                    [remove(r, DUPLICATE_REPLY) for r in rs[1:]],
                    rs[0],
                )[1],
            )
        ),
    )


def process_post(submission):
    """
    Process a submission, remove illegal replies and update flare if needed.
    """
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
                filter(
                    lambda r: r.banned_by is None and r.author
                ),  # Filter out removed replies.
                filter(is_valid),  # Filter out invalid replies.
                leave_only(
                    (lambda r: comment.author != r.author, SELF_REPLY)
                ),  # Filter out self replies, remove the rest.
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
    process_post(do(print)(reddit.submission(id="ivsz3y")))


def print_removal_reason_ids():
    reasons = subreddit.mod.removal_reasons
    for reason in reasons:
        print(
            "Title: {}\nText: {}\nID: {}\n\n\n".format(
                *map(get_display)([reason.title, reason.message, reason.id])
            )
        )


def check_hot():
    for submission in subreddit.hot(limit=CHECK_HOT):
        if not submission.stickied:
            process_post(submission)


def check_reports():
    for submission in subreddit.mod.reports():
        process_post(submission)
        submission.mod.approve()


def main():
    while True:
        print("\n\n\nHere we go again!")
        try:
            check_hot()
            time.sleep(120)
        except prawcore.exceptions.ServerError:
            pass


if __name__ == "__main__":
    main()
