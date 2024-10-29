# WMCore-Jenkins: Declarative Jenkins Pipelines for WMCore

This respository contains Jenkinsfiles that configure Jenkins Pipelines used to run tests for the [dmwm/WMCore](https://github.com/dmwm/WMCore) project.

## Repository Structure

* `WMCore-Aggregate-Baseline`: Contains the Jenkinsfile to aggregate the baseline unittest results
* `WMCore-PR-pylint`: Contains the Jenkinsfile to run pylint tests for a PR
* `WMCore-PR-Report`: Contains the Jenkins file to run tests suites triggered by a PR
  * Triggers`WMCore-PR-pylint` and `WMCore-PR-test`
* `WMCore-PR-test`: Contains the Jenkinsfile to run unit tests for a PR
* `WMCore-TagBaseline`: Contains the Jenkinsfile to tag latest WMCore, run via cronjob
* `WMCore-Test-Base`: Contains files shared between all tests
    * `docker-compose.yml`: Configuration to run test containers
    * `setup-env.sh`: Copies and modifies the necessary files, creates necessary directories in the Jenkins $WORKSPACE
    * `run_local.sh`: Sets environment variables when wanting to test locally
* `WMCore-unittests-baseline`: Contains the Jenksinfile to run baseline unittests
* `docker/wmcore`: The custom test image in which tests are ran in
    * Contains the necessary scripts and dependencies to run unittests and linting
    * Currently, the custom test image is located in the CMS Registry
      * registry.cern.ch/cmsweb/wmcore-dev

## Equivalent Jenkins Jobs/Pipeline
| Original Job/Test           | New Pipeline/Test         | Description                                                                         |
| :-------------------------- | :------------------------ | :---------------------------------------------------------------------------------- |
| DMWM-WMCore-TagBaseline     | WMCore-TagBaseline        |                                                                                     |
| DMWM-WMAgentPy3-TestAll     | WMCore-Unittest-Baseline  |                                                                                     |
| DMWM-WMCore-TestOracle      |                           |                                                                                     |
| DMWM-WMCorePy3-UnitTests    | WMCore-Aggregate-Baseline |                                                                                     |
| DMWM-WMCore-PR-test         | WMCore-PR-Report          | Triggered by PR in `dmwm/WMCore`, runs PR-pylint and PR-Test and reports back to PR |
| DMWM-WMCore-PR-pylintpy3    | WMCore-PR-pylint          | Runs pylint tests, triggered by WMCore-PR-Report                                    |
| DMWM-WMCorePy3-PR-unittests | WMCore-PR-Test            | Runs WMCore Unit tests on a PR, triggered by WMCore-PR-Report                       |
