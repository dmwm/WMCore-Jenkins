#! /usr/bin/env python

import os
import sys
import time

from github import Github

try:
    token = os.environ['DMWMBOT_TOKEN2']
    print('DMWMBOT_TOKEN2 was defined')
except KeyError:
    print('DMWMBOT_TOKEN2 was not defined')

try:
    gh = Github(os.environ['DMWMBOT_TOKEN'])
except KeyError:
    print('DMWMBOT_TOKEN not defined. Not updating PR')
    sys.exit()

codeRepo = os.environ.get('CODE_REPO', 'WMCore')
teamName = os.environ.get('WMCORE_REPO', 'dmwm')
repoName = '%s/%s' % (teamName, codeRepo)

issueID = None

if 'ghprbPullId' in os.environ:
    issueID = os.environ['ghprbPullId']
    mode = 'PR'
elif 'TargetIssueID' in os.environ:
    issueID = os.environ['TargetIssueID']
    mode = 'Daily'

print("Looking for %s issue %s" % (repoName, issueID))

repo = gh.get_repo(repoName)
issue = repo.get_issue(int(issueID))
reportURL = os.environ['BUILD_URL']

lastCommit = repo.get_pull(int(issueID)).get_commits().get_page(0)[-1]
lastCommit.create_status(state='pending', target_url=reportURL,
                         description='Tests started at ' + time.strftime("%d %b %Y %H:%M GMT"))
