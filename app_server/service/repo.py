#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Provide some basic higher level version control functions
   simplified for our application (i.e. working with single files
   isolated in different directories).

   This DOES NOT ALLOW SAFE CONCURRENT ACCESS to a shared `repodir`
"""
from __future__ import print_function, division, unicode_literals

import os
import sys
import subprocess

import git  #Ubuntu/Debian: apt-get install python-git
from git.exc import InvalidGitRepositoryError, NoSuchPathError

class RepoError(Exception):
    pass


def check(repodir, commit_id=None):
    """Make sure that:
          -- Repo path exists
          -- There are no uncommitted changes
          -- The repo isn't empty
          -- The latest commit is `commit_id`

       Translates exceptions into `RepoError` for the application
       where relevant.
    """
    try:
        r = git.Repo(repodir)
    except NoSuchPathError:
        raise RepoError("Path")
    except InvalidGitRepositoryError:
        raise RepoError("Format")
    if r.is_dirty():
        raise RepoError("Uncommitted")
    log = r.head.log()
    if not log:
        raise RepoError("Empty")
    if not commit_id is None:
        if log[-1].newhexsha != commit_id:
            raise RepoError("Inconsistent")
    return True


def init(repodir):
    git.Repo.init(repodir)


def commit(repodir, fbasename, message):
    """Ideally repo.check() has been called already externally.
       `fbasename` is assumed to be in `repodir`
    """
    r = git.Repo(repodir)
    filename = os.path.join(repodir, fbasename)
    r.index.add([filename])
    c = r.index.commit(message)
    return c.hexsha


def revert(repodir, fbasename, commit_id, message=None):
    """Ideally repo.check() has been called already externally.

       This checks out a file at previous commit and recommits it,
       i.e. reverts a file without losing subsequent edit history.
    """
    r = git.Repo(repodir)
    r.git.checkout(commit_id, fbasename)
    if message is None:
        message = "reverted '{}' to {}".format(fbasename, commit_id)
    return commit(repodir, fbasename, message)


def rollback(repodir, commit_id=None):
    """This is a HARD ROLLBACK to a previous commit, i.e. subsequent
       history is lost. This should not be used by users to undo
       recent saves (use `revert` instead), but may be used by scripts
       to recover from errors such as partial commits.

       The previous commit (HEAD) is used if `commit_id` is None
    """
    r = git.Repo(repodir)
    r.git.reset("--hard", commit_id)



def test():
    """Informal tests...
    """
    import os
    import tempfile
    import repo
    ### 1
    try:
        repo.check("/non_existent")
    except repo.RepoError as e:
        assert str(e) == "Path"
        print("TEST_1 SUCCESS:", "Invalid path caught!")
    tempd = tempfile.mkdtemp(prefix="repo_")
    ### 2
    try:
        repo.check(tempd)
    except repo.RepoError as e:
        assert str(e) == "Format"
        print("TEST_2 SUCCESS:", "Not a repo caught!")
    #CREATE REPO
    repodir = os.path.join(tempd, "test")
    repo.init(repodir)
    ### 3
    try:
        repo.check(repodir)
    except repo.RepoError as e:
        assert str(e) == "Empty"
        print("TEST_3 SUCCESS:", "Empty repo caught!")
    #CREATE FILE AND COMMIT
    fbasename = "a"
    filename = os.path.join(repodir, fbasename)
    with open(filename, "w") as wfh:
        wfh.write("first edits\n")
    cid1 = repo.commit(repodir, fbasename, "commit 1")
    print("Commited file to repo, commit id:", cid1)
    ### 4
    try:
        repo.check(repodir, cid1 + "not_correct_id")
    except repo.RepoError as e:
        assert str(e) == "Inconsistent"
        print("TEST_4 SUCCESS:", "Wrong commit ID caught!")
    #CREATE PARTIAL COMMIT
    repo.check(repodir, cid1)
    with open(filename, "w") as wfh:
        wfh.write("unsuccessful edits\n")
    r = git.Repo(repodir)
    r.index.add([filename])
    ### 5
    try:
        repo.check(repodir, cid1)
    except repo.RepoError as e:
        assert str(e) == "Uncommitted"
        print("TEST_5 SUCCESS:", "Partial commit process caught!")
    #
    repo.rollback(repodir)
    repo.check(repodir, cid1)
    with open(filename, "w") as wfh:
        wfh.write("successful edits\n")
    cid2 = repo.commit(repodir, fbasename, "commit 2")
    print("Commited file update to repo, commit id:", cid2)
    ### 6
    repo.check(repodir, cid2)    
    cid3 = repo.revert(repodir, fbasename, cid1)
    print("Reverting file to first commit, new commit id:", cid3)
    if repo.check(repodir, cid3) and open(filename).read() == "first edits\n":
        print("TEST_6 SUCCESSFUL:", "Successfully reverted file to previous version")
    


if __name__ == "__main__":
    test()
