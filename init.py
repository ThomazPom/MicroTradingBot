import os, git


def clone_and_rename(url, src, dest):
    if not os.path.exists("") and not os.path.exists(dest):
        print("Git clone ..")
        git.Git("./").clone(url)

    if os.path.exists(src) and not os.path.exists(dest):
        print("Rename")
        os.rename(src, dest)


clone_and_rename("https://github.com/veox/python3-krakenex", "python3-krakenex", "python3krakenex")
clone_and_rename("https://github.com/websocket-client/websocket-client", "websocket-client", "websocket_client")
