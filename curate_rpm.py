#!/usr/bin/env python3

### IMPORTS ###
import json
import logging
import os
import subprocess

### GLOBALS ###

### FUNCTIONS ###
def get_packages_from_payload(payload_json):
    logging.debug("Getting the list of packages file from the payload.")
    logging.debug("  payload_json: %s", payload_json)
    payload_dict = json.loads(payload_json)
    logging.debug("  payload_dict: %s", payload_json)
    pkg_contents = payload_dict['packages']
    logging.debug("  pkg_contents: %s", pkg_contents)
    return pkg_contents

### CLASSES ###
class RPMPackagePuller:
    def __init__(self, login_data, package_line):
        self.logger = logging.getLogger(type(self).__name__)
        self.login_data = login_data
        self.package_line = package_line
        self.to_copy = []
        self.success = False
        self.logger.debug("RPMPackagePuller for package: %s", self.package_line)

    def _install_package(self):
        self.logger.debug("Getting the package")
        yum_cmd = "yum install --downloadonly {}".format(
            self.package_line
        )
        yum_output = subprocess.run(yum_cmd.split(' '), stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        self.logger.debug("  yum_output: %s", yum_output)
        # Check for a failed install
        if yum_output.returncode is not 0:
            # NOTE: Since the output from the yum command is captured, it is
            #       possible to parse the output and figure out which dependency
            #       failed.  This isn't required for this example as the failed
            #       curation will be referred to manual review.
            self.logger.warning("Failed to install package: %s", self.package_line)
            self.logger.warning("  Error: %s", yum_output.stderr.decode())
            return
        # Install succeeded, so process the output
        self.success = True
        tmp_output = yum_output.stdout.decode().splitlines()
        self.logger.debug("  yum_output.stdout: %s", tmp_output)
        # FIXME: What is the stdout format for yum?
        # for item in tmp_output:
        #     if item[0:13] == "  Downloading":
        #         tmp_pkg_split = item.split(" ")
        #         self.logger.debug("  tmp_pkg_split: %s", tmp_pkg_split)
        #         tmp_pkg_split2 = tmp_pkg_split[3].split('/')
        #         self.logger.debug("  tmp_pkg_split2: %s", tmp_pkg_split2)
        #         self.to_copy.append("/".join(tmp_pkg_split2[9:]))
        self.logger.debug("  self._to_copy: %s", self.to_copy)

    def _copy_to_local(self):
        self.logger.debug("Copying package and dependencies to local repo")
        for pkg in self.to_copy:
            self.logger.debug("  pkg: %s", pkg)
            # FIXME: Is the '-cache' part needed for the RPM repos?
            curl_cmd = "curl -f -XPOST -u{}:{} {}/api/copy/{}/{}?to=/{}/{}".format(
                self.login_data['user'],
                self.login_data['apikey'],
                self.login_data['arti_url'],
                "{}-cache".format(self.login_data['remote_repo']),
                pkg,
                self.login_data['local_repo'],
                pkg
            )
            curl_output = subprocess.run(curl_cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.logger.debug("  curl_output: %s", curl_output)

    def curate(self):
        self.logger.info("Curating RPM package: %s", self.package_line)
        # Should figure out how to configure pip to pull from remote repo...
        self._install_package()
        self._copy_to_local()

### MAIN ###
def main():
    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG
    )

    logging.debug("Environment Prep Starting")
    tmp_payload_json = os.environ['res_curaterpm_payload']
    tmp_packages = get_packages_from_payload(tmp_payload_json)

    tmp_login_data = {}
    tmp_login_data['user'] = os.environ['int_artifactory_user']
    tmp_login_data['apikey'] = os.environ['int_artifactory_apikey']
    tmp_login_data['arti_url'] = os.environ['int_artifactory_url']
    tmp_login_data['local_repo'] = os.environ['local_repo_name']
    tmp_login_data['remote_repo'] = os.environ['remote_repo_name']

    tmp_rpmpackagepullers = []
    for tmp_pkg in tmp_packages:
        tmp_rpmpackagepullers.append(RPMPackagePuller(tmp_pkg))
    for tmp_puller in tmp_rpmpackagepullers:
        tmp_puller.curate()

    # Report Results
    # NOTE: This just prints the results to the log output.  This information
    #       can be gathered and pushed to a webhook on an external system for
    #       reporting, e.g. JIRA or ServiceNow.
    logging.info("Gathering Results")
    tmp_successes = []
    tmp_failures = []
    for tmp_puller in tmp_rpmpackagepullers:
        if tmp_puller.success:
            tmp_successes.append(tmp_puller.package_line)
        else:
            tmp_failures.append(tmp_puller.package_line)
    logging.info("Successfully Curated:")
    for item in tmp_successes:
        logging.info("  %s", item)
    if len(tmp_failures) > 0:
        logging.warning("Failed to Curate:")
        for item in tmp_failures:
            logging.warning("  %s", item)

if __name__ == '__main__':
    main()
