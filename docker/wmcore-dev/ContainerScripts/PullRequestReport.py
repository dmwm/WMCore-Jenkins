#! /usr/bin/env python

from __future__ import print_function

import glob
import json
import os
import time
import traceback
from collections import defaultdict

import jinja2
import xunitparser
from github import Github

pylintReportFile = 'pylint.jinja'
pylint3kReportFile = 'pylint3k.jinja'
pylintSummaryFile = 'pylintSummary.jinja'
unitTestSummaryFile = 'unitTestReport.jinja'
pyfutureSummaryFile = 'pyfutureSummary.jinja'
pycodestyleReportFile = 'pycodestyle.jinja'

okWarnings = ['0511', '0703', '0613']

summaryMessage = ''
longMessage = ''
reportOn = {}
failed = False


def buildPylintReport(templateEnv, fileName="pylintReport.json"):
    """
    Parse the Pylint reports
    :param templateEnv: string with the Jinja2 template name
    :param fileName: string with the report file name
    """
    pyName = "Python2" if fileName == "pylintReport.json" else "Python3"
    print("Evaluating pylint report for file: {}".format(fileName))
    try:
        with open('LatestPylint/{}'.format(fileName), 'r') as reportFile:
            report = json.load(reportFile)
    except IOError:
        print("File {} not found.".format(fileName))
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


def buildPylint3kReport(templateEnv):
    fileName = "pylint3kReport.json"
    print("Evaluating pylint report for file: {}".format(fileName))
    try:
        with open('LatestPylint/{}'.format(fileName), 'r') as reportFile:
            report = json.load(reportFile)
    except IOError:
        print("File {} not found.".format(fileName))
        return None, None

    pylintReportTemplate = templateEnv.get_template(pylint3kReportFile)
    # Process the template to produce our final text.
    pylintReport = pylintReportTemplate.render({'report': report, 'okWarnings': okWarnings})

    pylintSummary = {'errors': 0, 'warnings': 0, 'comments': 0}
    for filename in report:
        summary = report[filename]['test']
        for prop in pylintSummary:
            pylintSummary[prop] += summary[prop]

    return pylintReport, pylintSummary


def buildPyCodeStyleReport(templateEnv, inputFileName="pep8.txt"):
    """
    Build the report for pycodestyle (also known as pep8)
    """
    print("Evaluating pep8 style report for file: {}".format(inputFileName))

    errors = defaultdict(list)
    pycodestyleReportHTML = None
    pycodestyleSummary = {'comments': 0}

    try:
        with open('LatestPylint/{}'.format(inputFileName), 'r') as reportFile:
            for line in reportFile:
                pycodestyleSummary['comments'] += 1
                fileName, line, error = line.split(':', 2)
                error = error.lstrip().lstrip('[')
                errorCode, message = error.split('] ', 1)
                errors[fileName].append((line, errorCode, message))
        pycodestyleReportTemplate = templateEnv.get_template(pycodestyleReportFile)
        pycodestyleReportHTML = pycodestyleReportTemplate.render({'report': errors})
    except IOError:
        print("File {} not found.".format(inputFileName))
    except Exception:
        print("Was not able to open or parse pycodestyle tests")
        traceback.print_exc()

    return False, pycodestyleReportHTML, pycodestyleSummary

def buildUnitTestReport(templateEnv, pyName="Python2"):
    """
    Builds the python2/python3 unit test report
    :param templateEnv: string with the name of the jinja template
    :param pyName: string with either a Python2 or Python3 value
    :return:
    """
    if pyName not in ("Python2", "Python3"):
        print("Actually, you passed an invalid python name argument!")
        raise RuntimeError()

    print("Evaluating base/test {} unit tests report files".format(pyName))
    unstableTests = []
    testResults = {}

    try:
        with open('UnstableTests.txt') as unstableFile:
            for line in unstableFile:
                unstableTests.append(line.strip())
    except:
        print("Was not able to open list of unstable tests")

    filePattern = '*/nosetests-*.xml' if pyName == "Python2" else '*/nosetestspy3-*.xml'
    for kind, directory in [('base', './MasterUnitTests/'), ('test', './LatestUnitTests/')]:
        print("Scanning directory %s" % directory)
        for xunitFile in glob.iglob(directory + filePattern):
            print("Opening file %s" % xunitFile)
            with open(xunitFile) as xf:
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
    print("{} Unit Test summary {}".format(pyName, unitTestSummary))
    return failed, unitTestSummaryHTML, unitTestSummary


def buildPyFutureReport(templateEnv):
    print("Evaluating futurize reports")

    pyfutureSummary = {}
    failed = False

    try:
        with open('LatestFuturize/added.message', 'r') as messageFile:
            lines = messageFile.readlines()
            if len(lines):
                lt = [l.strip() for l in lines]
                lt1 = [l for l in lt if l]
                lt2 = [l.replace("*", "") for l in lt1]
                pyfutureSummary['added.message'] = lt2
                failed = True
    except:
        print("Was not able to open file added.message")

    try:
        with open('LatestFuturize/test.patch', 'r') as patchFile:
            lines = patchFile.readlines()
            if len(lines):
                pyfutureSummary['test.patch'] = lines
                failed = True
    except:
        print("Was not able to open file test.patch")

    try:
        with open('LatestFuturize/idioms.patch', 'r') as patchFile:
            lines = patchFile.readlines()
            if len(lines):
                pyfutureSummary['idioms.patch'] = lines
    except:
        print("Was not able to open file idioms.patch")

    pyfutureSummaryTemplate = templateEnv.get_template(pyfutureSummaryFile)
    pyfutureSummaryHTML = pyfutureSummaryTemplate.render(
        {'report': pyfutureSummary, 'filenames': sorted(pyfutureSummary.keys())})

    return failed, pyfutureSummary, pyfutureSummaryHTML


### main code
# load jinja templates first
templateLoader = jinja2.FileSystemLoader(searchpath="templates/")
templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True, lstrip_blocks=True)

# Build Python2 Pylint report from jenkins artifacts
failedPylint, pylintSummaryHTML, pylintReport, pylintSummary = buildPylintReport(templateEnv)
# Build Python3 Pylint report from jenkins artifacts (NOTE: most of the projects don't have it yet)
failedPylintPy3, pylintSummaryHTMLPy3, pylintReportPy3, pylintSummaryPy3 = buildPylintReport(templateEnv,
                                                                                             "pylintpy3Report.json")
# Build Python2 Pylint --py3k report from jenkins artifacts
pylintReport3k, pylintSummary3k = buildPylint3kReport(templateEnv)
failedPyFuture, pyfutureSummary, pyfutureSummaryHTML = buildPyFutureReport(templateEnv)
try:
    failedPycodestyle, pycodestyleReport, pycodestyleSummary = buildPyCodeStyleReport(templateEnv, "pep8py3.txt")
except:
    # then fallback to pep8.txt file instead
    failedPycodestyle, pycodestyleReport, pycodestyleSummary = buildPyCodeStyleReport(templateEnv)

# not all projects have unit tests. First, try to create the Python2 based unit tests
try:
    py2FailedUnitTests, py2UnitTestSummaryHTML, py2UnitTestSummary = buildUnitTestReport(templateEnv, pyName="Python2")
except (IOError, RuntimeError):
    py2FailedUnitTests, py2UnitTestSummaryHTML, py2UnitTestSummary = 0, '', {}
# Now try to create the Python3 based unit tests
try:
    py3FailedUnitTests, py3UnitTestSummaryHTML, py3UnitTestSummary = buildUnitTestReport(templateEnv, pyName="Python3")
except (IOError, RuntimeError):
    py3FailedUnitTests, py3UnitTestSummaryHTML, py3UnitTestSummary = 0, '', {}


with open('artifacts/PullRequestReport.html', 'w') as html:
    if py3UnitTestSummary:
        html.write(py3UnitTestSummaryHTML)
    if py2UnitTestSummary:
        html.write(py2UnitTestSummaryHTML)
    if pylintSummaryHTML:
        html.write(pylintSummaryHTML)
    if pylintReport:
        html.write(pylintReport)
    if pylintSummaryPy3:
        html.write(pylintSummaryHTMLPy3)
        html.write(pylintReportPy3)
    if pylintSummary3k:
        html.write(pylintReport3k)
    if pycodestyleReport:
        html.write(pycodestyleReport)
    if pyfutureSummary:
        html.write(pyfutureSummaryHTML)

gh = Github(os.environ['DMWMBOT_TOKEN'])
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


if py2UnitTestSummary:  # Some repos have no unit tests
    message += ' * Python2 Unit tests: %s\n' % statusMap[py2FailedUnitTests]['readStatus']
    if py2UnitTestSummary['newFailures']:
        message += '   * %s new failures\n' % py2UnitTestSummary['newFailures']
    if py2UnitTestSummary['deleted']:
        message += '   * %s tests deleted\n' % py2UnitTestSummary['deleted']
    if py2UnitTestSummary['okChanges']:
        message += '   * %s tests no longer failing\n' % py2UnitTestSummary['okChanges']
    if py2UnitTestSummary['added']:
        message += '   * %s tests added\n' % py2UnitTestSummary['added']
    if py2UnitTestSummary['unstableChanges']:
        message += '   * %s changes in unstable tests\n' % py2UnitTestSummary['unstableChanges']

if py3UnitTestSummary:  # Most of the repositories do not yet have python3 unit tests
    message += ' * Python3 Unit tests: %s\n' % statusMap[py3FailedUnitTests]['readStatus']
    if py3UnitTestSummary['newFailures']:
        message += '   * %s new failures\n' % py3UnitTestSummary['newFailures']
    if py3UnitTestSummary['deleted']:
        message += '   * %s tests deleted\n' % py3UnitTestSummary['deleted']
    if py3UnitTestSummary['okChanges']:
        message += '   * %s tests no longer failing\n' % py3UnitTestSummary['okChanges']
    if py3UnitTestSummary['added']:
        message += '   * %s tests added\n' % py3UnitTestSummary['added']
    if py3UnitTestSummary['unstableChanges']:
        message += '   * %s changes in unstable tests\n' % py3UnitTestSummary['unstableChanges']

if pylintSummary:
    message += ' * Python2 Pylint check: %s\n' % statusMap[failedPylint]['readStatus']
    if pylintSummary['failures']:
        message += '   * %s warnings and errors that must be fixed\n' % pylintSummary['failures']
    if pylintSummary['warnings']:
        message += '   * %s warnings\n' % pylintSummary['warnings']
    if pylintSummary['comments']:
        message += '   * %s comments to review\n' % pylintSummary['comments']

if pylintSummaryPy3:
    message += ' * Python3 Pylint check: %s\n' % statusMap[failedPylintPy3]['readStatus']
    if pylintSummaryPy3['failures']:
        message += '   * %s warnings and errors that must be fixed\n' % pylintSummaryPy3['failures']
    if pylintSummaryPy3['warnings']:
        message += '   * %s warnings\n' % pylintSummaryPy3['warnings']
    if pylintSummaryPy3['comments']:
        message += '   * %s comments to review\n' % pylintSummaryPy3['comments']

failedPy3k = False
if pylintSummary3k:
    failedPy3k = bool(pylintSummary3k['errors'] or pylintSummary3k['warnings'])
    message += ' * Pylint py3k check: %s\n' % statusMap[failedPy3k]['readStatus']
    if pylintSummary3k['errors']:
        message += '   * %s errors and warnings that should be fixed\n' % pylintSummary3k['errors']
    if pylintSummary3k['warnings']:
        message += '   * %s warnings\n' % pylintSummary3k['warnings']
    if pylintSummary3k['comments']:
        message += '   * %s comments to review\n' % pylintSummary3k['comments']

message += ' * Pycodestyle check: %s\n' % statusMap[failedPycodestyle]['readStatus']
if pycodestyleSummary['comments']:
    message += '   * %s comments to review\n' % pycodestyleSummary['comments']

if pyfutureSummary:
    message += ' * Python3 compatibility checks: %s\n' % statusMap[failedPyFuture]['readStatus']
    if failedPyFuture:
        message += '   * fails python3 compatibility test\n '
    if 'idioms.patch' in pyfutureSummary and pyfutureSummary['idioms.patch']:
        message += '   * there are suggested fixes for newer python3 idioms\n '

message += "\nDetails at %s\n" % reportURL
status = issue.create_comment(message)

timeNow = time.strftime("%d %b %Y %H:%M GMT")
lastCommit = repo.get_pull(int(issueID)).get_commits().get_page(0)[-1]

if pylintSummary:
    lastCommit.create_status(state=statusMap[failedPylint]['ghStatus'], target_url=reportURL + '#pylintpy2',
                             description='Finished at %s' % timeNow, context='Py2 Pylint')
if pylintSummaryPy3:
    lastCommit.create_status(state=statusMap[failedPylint]['ghStatus'], target_url=reportURL + '#pylintpy3',
                             description='Finished at %s' % timeNow, context='Py3 Pylint')
if pylintSummary3k:
    lastCommit.create_status(state=statusMap[failedPy3k]['ghStatus'], target_url=reportURL + '#pylint3k',
                             description='Finished at %s' % timeNow, context='Pylint --py3k')
if py2UnitTestSummary:
    lastCommit.create_status(state=statusMap[py2FailedUnitTests]['ghStatus'], target_url=reportURL + '#unittestspy2',
                             description='Finished at %s' % timeNow, context='Py2 Unit tests')
if py3UnitTestSummary:
    lastCommit.create_status(state=statusMap[py3FailedUnitTests]['ghStatus'], target_url=reportURL + '#unittestspy3',
                             description='Finished at %s' % timeNow, context='Py3 Unit tests')
if pyfutureSummary:
    lastCommit.create_status(state=statusMap[failedPyFuture]['ghStatus'], target_url=reportURL + '#pyfuture',
                             description='Finished at %s' % timeNow, context='Python3 compatibility')

if pylintSummary:
    if failedPylint:
        print('Testing of python code. DMWM-FAIL-PYLINT')
    else:
        print('Testing of python code. DMWM-SUCCEED-PYLINT')

if pylintSummaryPy3:
    if failedPylintPy3:
        print('Testing of python code. DMWM-FAIL-PYLINTPY3')
    else:
        print('Testing of python code. DMWM-SUCCEED-PYLINTPY3')

if pylintSummary3k:
    if failedPy3k:
        print('Testing of python code. DMWM-FAIL-PYLINT3K')
    elif pylintSummary3k:
        print('Testing of python code. DMWM-SUCCEED-PYLINT3k')

if py2UnitTestSummary:
    if py2FailedUnitTests:
        print('Testing of python code. DMWM-FAIL-PY2-UNIT')
    else:
        print('Testing of python code. DMWM-SUCCEED-PY2-UNIT')

if py3UnitTestSummary:
    if py3FailedUnitTests:
        print('Testing of python code. DMWM-FAIL-PY3-UNIT')
    else:
        print('Testing of python code. DMWM-SUCCEED-PY3-UNIT')

if pyfutureSummary:
    if failedPyFuture:
        print('Testing of python code. DMWM-FAIL-PY27')
    else:
        print('Testing of python code. DMWM-SUCCEED-PY27')
