#! /usr/bin/env python
'''
PullRequestReport.py

Generates a pull request report from a pylint report, pylint summary,
nosetests summary, and pycodestyle

Input files are located in the directory of script execution

Environment Variables:
    JENKINS_JINJA_TEMPLATE_PATH: Location of Jinja2 Templates
    DMWMBOT_TOKEN: GitHub token
    CODE_REPO: Code repository name
    WMCORE_REPO: Project name
    ghprbPullId (optional): PR ID from Jenkins GitHub Pull Request Builder
    TargetIssueID (optional)
    BUILD_URL: Jenkins build URL; for report location

Input Files:
    pylintpy3Report.json: pylint report
    pep8py3.txt: pycodestyle report
    UnstableTests.txt: unstable unittests
    MasterUnitTests/*/nosetestspy3-*.xml: Baseline unittest results
    LatestUnitTests/*/nosetestspy3-*.xml: PR unittest results

Output Files:
    artifacts/PullReqequestReport.html
'''

from __future__ import print_function

from collections import defaultdict
import glob
import json
import os
from pathlib import Path
import sys
import time
import traceback

import jinja2
from jinja2.exceptions import TemplateNotFound
import xunitparser
from github import Github

pylintReportFile = 'pylint.jinja'
pylintSummaryFile = 'pylintSummary.jinja'
unitTestSummaryFile = 'unitTestReport.jinja'
pycodestyleReportFile = 'pycodestyle.jinja'

okWarnings = ['0511', '0703', '0613']

summaryMessage = ''
longMessage = ''
reportOn = {}
failed = False


def buildPylintReport(templateEnv, fileName="pylintpy3Report.json"):
    """
    Parse the Pylint reports

    :param templateEnv: string with the Jinja2 template name
    :param fileName: string with the file name of the report to be parsed

    :returns: failedPylintPy3, pylintSummaryHTMLPy3, pylintReportPy3, pylintSummaryPy3
    """
    pyName = "Python3"
    print(f"Evaluating pylint report for file: {fileName}")
    try:
        with open(f'LatestPylint/{fileName}', 'r') as reportFile:
            report = json.load(reportFile)
    except IOError:
        print(f"File {fileName} not found.")
        return False, None, None, None

    pylintReportTemplate = templateEnv.get_template(pylintReportFile)
    pylintSummaryTemplate = templateEnv.get_template(pylintSummaryFile)

    # Process the template to produce our final text.
    pylintReport = pylintReportTemplate.render({'report': report, 'okWarnings': okWarnings})
    pylintSummaryHTML = pylintSummaryTemplate.render({'whichPython': pyName, 'report': report,
                                                      'filenames': sorted(report.keys())})

    # Figure out if pylint failed
    failed = False
    failures = 0
    warnings = 0
    comments = 0
    for filename in report.keys():
        if 'test' in report[filename]:
            for event in report[filename]['test']['events']:
                if event[1] in ['W', 'E'] and event[2] not in okWarnings:
                    failed = True
                    failures += 1
                elif event[1] in ['W', 'E']:
                    warnings += 1
                else:
                    comments += 1
            if report[filename]['test'].get('score', None):
                if float(report[filename]['test']['score']) < 9 and (float(report[filename]['test']['score']) <
                                                                     float(report[filename]['base'].get('score', 0))):
                    failed = True
                elif float(report[filename]['test']['score']) < 8:
                    failed = True

    pylintSummary = {'failures': failures, 'warnings': warnings, 'comments': comments}
    return failed, pylintSummaryHTML, pylintReport, pylintSummary


def buildPyCodeStyleReport(templateEnv, inputFileName="pep8py3.txt"):
    """
    Build the report for pycodestyle (also known as pep8)

    :param templateEnv: string with the Jinja2 template name
    :param inputFileName: string with the file name of the report to be parsed

    :returns: bool failedPycodestyle, str pycodestyleReport html, dict pycodestyleSummary
    """

    print(f"Evaluating pep8 style report for file: {inputFileName}")

    errors = defaultdict(list)
    pycodestyleReportHTML = None
    pycodestyleSummary = {'comments': 0}

    try:
        with open(f'LatestPylint/{inputFileName}', 'r') as reportFile:
            for line in reportFile:
                pycodestyleSummary['comments'] += 1
                fileName, line, error = line.split(':', 2)
                error = error.lstrip().lstrip('[')
                errorCode, message = error.split('] ', 1)
                errors[fileName].append((line, errorCode, message))
        pycodestyleReportTemplate = templateEnv.get_template(pycodestyleReportFile)
        pycodestyleReportHTML = pycodestyleReportTemplate.render({'report': errors})
    except IOError:
        print(f"File {inputFileName} not found.")
    except TemplateNotFound:
        print(f"Template {pycodestyleReportFile} not found")
    except Exception:
        print("Was not able to open or parse pycodestyle tests")
        traceback.print_exc()

    return False, pycodestyleReportHTML, pycodestyleSummary

def buildUnitTestReport(templateEnv, pyName="Python3"):
    """
    Builds the python3 unit test report

    :param templateEnv: string with the name of the jinja template
    :param pyName: string with either a Python2 or Python3 value

    :returns: py3FailedUnitTests, py3UnitTestSummaryHTML, py3UnitTestSummary
    """
    if pyName not in ("Python2", "Python3"):
        print("Invalid python name argument!")
        raise RuntimeError()

    print(f"Evaluating base/test {pyName} unit tests report files")
    unstableTests = []
    testResults = {}

    try:
        with open('UnstableTests.txt', 'r') as unstableFile:
            for line in unstableFile:
                unstableTests.append(line.strip())
    except:
        print("Was not able to open list of unstable tests")

    filePattern = '*/nosetestspy3-*.xml'
    for kind, directory in [('base', './MasterUnitTests/'), ('test', './LatestUnitTests/')]:
        print("Scanning directory %s" % directory)
        for xunitFile in glob.iglob(directory + filePattern):
            print("Opening file %s" % xunitFile)
            with open(xunitFile, 'r') as xf:
                ts, tr = xunitparser.parse(xf)
                for tc in ts:
                    testName = '%s:%s' % (tc.classname, tc.methodname)
                    if testName in testResults:
                        testResults[testName].update({kind: tc.result})
                    else:
                        testResults[testName] = {kind: tc.result}
    if not testResults:
        print("No unit test results found!")
        raise RuntimeError()

    failed = False
    errorConditions = ['error', 'failure']

    newFailures = []
    unstableChanges = []
    okChanges = []
    added = []
    deleted = []

    for testName, testResult in sorted(testResults.items()):
        oldStatus = testResult.get('base', None)
        newStatus = testResult.get('test', None)
        if oldStatus and newStatus and testName in unstableTests:
            if oldStatus != newStatus:
                unstableChanges.append({'name': testName, 'new': newStatus, 'old': oldStatus})
        elif oldStatus and newStatus:
            if oldStatus != newStatus:
                if newStatus in errorConditions:
                    failed = True
                    newFailures.append({'name': testName, 'new': newStatus, 'old': oldStatus})
                else:
                    okChanges.append({'name': testName, 'new': newStatus, 'old': oldStatus})
        elif newStatus:
            added.append({'name': testName, 'new': newStatus, 'old': oldStatus})
            if newStatus in errorConditions:
                failed = True
        elif oldStatus:
            deleted.append({'name': testName, 'new': newStatus, 'old': oldStatus})

    unitTestSummaryTemplate = templateEnv.get_template(unitTestSummaryFile)
    unitTestSummaryHTML = unitTestSummaryTemplate.render({'whichPython': pyName,
                                                          'newFailures': newFailures,
                                                          'added': added,
                                                          'deleted': deleted,
                                                          'unstableChanges': unstableChanges,
                                                          'okChanges': okChanges,
                                                          'errorConditions': errorConditions,
                                                          })

    unitTestSummary = {'newFailures': len(newFailures), 'added': len(added), 'deleted': len(deleted),
                       'okChanges': len(okChanges), 'unstableChanges': len(unstableChanges)}
    print(f"{pyName} Unit Test summary {unitTestSummary}")

    return failed, unitTestSummaryHTML, unitTestSummary


def reportToGithub(py3UnitTestSummary,
                   py3FailedUnitTests,
                   pylintSummaryPy3,
                   failedPylintPy3,
                   pycodestyleSummary):
    """
    Builds Report and GitHub Issue message
    """
    # Build GitHub Jenkins Results
    try:
        gh = Github(os.environ['DMWMBOT_TOKEN'])
    except KeyError:
        print('DMWMBOT_TOKEN not defined. Not updating PR')
        return
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

    repo = gh.get_repo(repoName)
    issue = repo.get_issue(int(issueID))
    reportURL = os.environ['BUILD_URL'].replace('jenkins/job',
                                                'jenkins/view/All/job') + 'artifact/artifacts/PullRequestReport.html'

    statusMap = {False: {'ghStatus': 'success', 'readStatus': 'succeeded'},
                 True: {'ghStatus': 'failure', 'readStatus': 'failed'}, }

    message = 'Jenkins results:\n'

    if py3UnitTestSummary:  # Most of the repositories do not yet have python3 unit tests
        message += (
            f' * Python3 Unit tests: '
            f'{statusMap[py3FailedUnitTests]["readStatus"]}\n'
        )
        if failures := py3UnitTestSummary['newFailures']:
            message += f'   * {failures} new failures\n'
        if deleted := py3UnitTestSummary['deleted']:
            message += f'   * {deleted} tests deleted\n'
        if okChanges := py3UnitTestSummary['okChanges']:
            message += f'   * {okChanges} tests no longer failing\n'
        if added := py3UnitTestSummary['added']:
            message += f'   * {added} tests added\n'
        if unstable := py3UnitTestSummary['unstableChanges']:
            message += f'   * {unstable} changes in unstable tests\n'

    if pylintSummaryPy3:
        message += (
            f' * Python3 Pylint check: '
            f'{statusMap[failedPylintPy3]["readStatus"]}\n'
        )
        if pylintFails := pylintSummaryPy3['failures']:
            message += (
                f'   * {pylintFails} warnings and errors that must be fixed\n'
            )
        if warnings := pylintSummaryPy3['warnings']:
            message += (
                f'   * {warnings} warnings\n'
            )
        if comments := pylintSummaryPy3['comments']:
            message += (
                f'   * {comments} comments to review\n'
            )

    message += (
        f' * Pycodestyle check: '
        f'{statusMap[failedPycodestyle]["readStatus"]}\n'
    )
    if comments := pycodestyleSummary['comments']:
        message += f'   * {comments} comments to review\n'

    message += f"\nDetails at {reportURL}\n"

    # GitHub PRs and Issues share the same number pool,
    # so there won't be a PR with the same number as an issue

    status = issue.create_comment(message)

    timeNow = time.strftime("%d %b %Y %H:%M GMT")
    lastCommit = repo.get_pull(int(issueID)).get_commits().get_page(0)[-1]

    if pylintSummaryPy3:
        lastCommit.create_status(
            state=statusMap[failedPylintPy3]['ghStatus'],
            target_url=reportURL + '#pylintpy3',
            description='Finished at %s' % timeNow, context='Py3 Pylint'
        )
    if py3UnitTestSummary:
        lastCommit.create_status(
            state=statusMap[py3FailedUnitTests]['ghStatus'],
            target_url=reportURL + '#unittestspy3',
            description='Finished at %s' % timeNow, context='Py3 Unit tests'
        )


if __name__ == '__main__':
    ### main code
    # load jinja templates
    try:
        templatePathEnv = os.environ["JENKINS_JINJA_TEMPLATE_PATH"]
        templatePath = Path(templatePathEnv)
        if not templatePath.exists():
            raise FileNotFoundError(f'{templatePath} not found')
        if not templatePath.is_dir():
            raise NotADirectoryError(f'{templatePath} is not a directory')
    except KeyError:
        print('JENKINS_JINJA_TEMPLATE_PATH not defined')
        raise

    templateLoader = jinja2.FileSystemLoader(searchpath=templatePath)
    templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True, lstrip_blocks=True)

    # Build Python3 Pylint report from jenkins artifacts (NOTE: most of the projects don't have it yet)
    failedPylintPy3, pylintSummaryHTMLPy3, pylintReportPy3, pylintSummaryPy3 = buildPylintReport(templateEnv,
                                                                                                 "pylintpy3Report.json")
    # Build pycodestyleReport
    try:
        failedPycodestyle, pycodestyleReport, pycodestyleSummary = buildPyCodeStyleReport(templateEnv, "pep8py3.txt")
    except:
        # then fallback to pep8.txt file instead
        failedPycodestyle, pycodestyleReport, pycodestyleSummary = buildPyCodeStyleReport(templateEnv)

    # Now try to create the Python3 based unit tests
    try:
        py3FailedUnitTests, py3UnitTestSummaryHTML, py3UnitTestSummary = buildUnitTestReport(templateEnv, pyName="Python3")
    except (IOError, RuntimeError):
        py3FailedUnitTests, py3UnitTestSummaryHTML, py3UnitTestSummary = 0, '', {}

    with open('artifacts/PullRequestReport.html', 'w') as html:
        if py3UnitTestSummary:
            html.write(py3UnitTestSummaryHTML)
        if pylintSummaryPy3:
            html.write(pylintSummaryHTMLPy3)
            html.write(pylintReportPy3)
        if pycodestyleReport:
            html.write(pycodestyleReport)

    reportToGithub(py3UnitTestSummary, py3FailedUnitTests, pylintSummaryPy3, failedPylintPy3, pycodestyleSummary)

    if pylintSummaryPy3:
        if failedPylintPy3:
            print('Testing of python code. DMWM-FAIL-PYLINTPY3')
        else:
            print('Testing of python code. DMWM-SUCCEED-PYLINTPY3')

    if py3UnitTestSummary:
        if py3FailedUnitTests:
            print('Testing of python code. DMWM-FAIL-PY3-UNIT')
        else:
            print('Testing of python code. DMWM-SUCCEED-PY3-UNIT')
