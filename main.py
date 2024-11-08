import os
from pprint import pprint
from dotenv import load_dotenv
from slack import get_thread_comments, auth_test, parse_comments
from comment import parse_texts, parse_text
from drive import upload_from_comment
from wiki import *

from utils import *

load_dotenv(override=True)

if __name__ == '__main__':
    channel_id = os.getenv("SLACK_CHANNEL_ID")
    thread_ts = os.getenv("SLACK_THREAD_TS")
    tmp_dir = os.path.join(os.getcwd(), "tmp", "data")
    os.makedirs(tmp_dir, exist_ok=True)
    

    local_repo_path = "tmp/repo.wiki"
    repo = os.getenv("GITHUB_WIKI_REPO_URL")
    md_file = os.getenv("GITHUB_WIKI_PAGE_NAME")
    
    # fetch comments
    
    comments = get_thread_comments(channel_id, thread_ts)
    parsed_comments = parse_comments(comments)
    parsed_comments.sort(key=lambda x: x['comment_datetime'])
    parsed_comments = parsed_comments[1:] # remove the first comment, which is the body of the thread
    print(f"Fetched all the comments of the thread({thread_ts}) in channel({channel_id}).\n Total comments: {len(parsed_comments)}")
    
    # parse comment contents
    # Avoid bottleneck by parsing the texts in parallels
    texts = [comment['content'] for comment in parsed_comments]
    for i, (parsed_comment, text) in enumerate(zip(parsed_comments, texts)):
        print(f"Start processing comment ({parsed_comment['id']})")
        parsed_text = parse_text(text)
        parsed_comment["json_data"] = parsed_text
        print(f"text parsed to json")
        
        # TODO better way
        if not parsed_comment['json_data'].get("workers"):
            parsed_comment['json_data']['workers'] = [get_team_name(parsed_comment['user_id'])]
        
        upload_from_comment(parsed_comment, tmp_dir)
        print(f"image uploaded to drive")
    

    # # remove tmp directory
    # os.rmdir(tmp_dir)
    
    # upload to wiki
    pull_repo(repo, local_repo_path)
    for i, comment in enumerate(parsed_comments):
        update_markdown(local_repo_path, md_file, comment, overwrite=(i==0))
    push_repo(local_repo_path, "Update devlogs")
    print("Wiki updated")