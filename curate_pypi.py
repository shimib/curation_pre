#!/usr/bin/env python3

### IMPORTS ###
import json
import logging
import os
import subprocess

### GLOBALS ###
REMOTE_REPO_NAME = "danielw-pypi-remote"
LOCAL_REPO_NAME = "danielw-pypi-local"

# These should be handled better, but need to be globals for now for CURL helper functions.
ARTIFACTORY_USER = os.environ['int_artifactory_user']
ARTIFACTORY_APIKEY = os.environ['int_artifactory_apikey']
ARTIFACTORY_URL = os.environ['int_artifactory_url']
PYPI_INDEX_URL = "{}//{}:{}@{}/artifactory/api/pypi/{}/simple".format(
    str(ARTIFACTORY_URL.split('/')[0]),
    ARTIFACTORY_USER,
    ARTIFACTORY_APIKEY,
    str(ARTIFACTORY_URL.split('/')[2]),
    REMOTE_REPO_NAME
)

### FUNCTIONS ###
def get_requirements_from_payload(payload_json):
    logging.debug("Getting the contents of the requirements.txt file from the payload.")
    logging.debug("  payload_json: %s", payload_json)
    payload_dict = json.loads(payload_json)
    logging.debug("  payload_dict: %s", payload_json)
    pkg_contents = payload_dict['packages']
    logging.debug("  pkg_contents: %s", pkg_contents)
    return pkg_contents

### CLASSES ###
class PythonPackagePuller:
    def __init__(self, package_line):
        self.logger = logging.getLogger(type(self).__name__)
        self.package_line = package_line
        self.local_repo = LOCAL_REPO_NAME
        self.remote_repo = REMOTE_REPO_NAME
        self.logger.debug("PythonPackagePuller for package: %s", self.package_line)
        self._packages_before_install = {}
        self._packages_after_install = {}
        self._package_changes = {}
        self._to_copy = []

    def _pip_get_current_packages(self):
        self.logger.debug("Getting the currently installed packages")
        pip_cmd = "pip freeze --disable-pip-version-check --no-color"
        pip_output = subprocess.run(pip_cmd.split(' '), stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        self.logger.debug("  pip_output: %s", pip_output)
        tmp_pkgs = {}
        for tmp_line in pip_output.stdout.decode().splitlines():
            self.logger.debug("  tmp_line: %s", tmp_line)
            tmp_pkg = tmp_line.split('==')
            if len(tmp_pkg) > 1: # Check to make sure the split happened, in case there's blank lines.
                tmp_pkgs[tmp_pkg[0]] = tmp_pkg[1]
        self.logger.debug("  tmp_pkgs: %s", tmp_pkgs)
        return tmp_pkgs

    def _install_package(self):
        self.logger.debug("Installing the package")
        # NOTE: A report option was added in pip v 22.2, but our installation isn't using that version currently.
        # NOTE: The image that is used to run this script should be kept in sync with the python version being used for
        #       development and deployment, otherwise there may be potential version misses.
        pip_cmd = "pip install --disable-pip-version-check --no-color --no-cache --ignore-installed --index-url {} {}".format(
            PYPI_INDEX_URL,
            self.package_line
        )
        pip_output = subprocess.run(pip_cmd.split(' '), stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        self.logger.debug("  pip_output: %s", pip_output)
        # FIXME: If the install fails, can we tell which package failed to install?
        if pip_output.returncode is not 0:
            self.logger.warning("Failed to install package: %s", self.package_line)
            self.logger.warning("  Error: %s", pip_output.stderr.decode())
            return
        tmp_output = pip_output.stdout.decode().splitlines()
        self.logger.debug("  pip_output.stdout: %s", tmp_output)
        for item in tmp_output:
            if item[0:13] == "  Downloading":
                tmp_pkg_split = item.split(" ")
                self.logger.debug("  tmp_pkg_split: %s", tmp_pkg_split)
                tmp_pkg_split2 = tmp_pkg_split[3].split('/')
                self.logger.debug("  tmp_pkg_split2: %s", tmp_pkg_split2)
                self._to_copy.append("/".join(tmp_pkg_split2[9:]))
        self.logger.debug("  self._to_copy: %s", self._to_copy)

    def _compare_packages(self):
        self.logger.debug("Comparing the package lists")
        pkg_diff = {}
        for tmp_pkg in self._packages_after_install:
            self.logger.debug("  tmp_pkg: %s", tmp_pkg)
            # Check if in the before and version matches, skip
            if tmp_pkg in self._packages_before_install:
                if self._packages_after_install[tmp_pkg] == self._packages_before_install[tmp_pkg]:
                    # Packages and versions match, so skipping:
                    continue
            # Packages and/or versions mismatch, so add to list
            pkg_diff[tmp_pkg] = self._packages_after_install[tmp_pkg]
        self.logger.debug("  pkg_diff: %s", pkg_diff)
        return pkg_diff

    def _copy_to_local(self):
        self.logger.debug("Copying package and dependencies to local repo")
        # FIXME: Do I need to copy the .pypi folder contents over?
        for pkg in self._to_copy:
            self.logger.debug("  pkg: %s", pkg)
            curl_cmd = "curl -f -XPOST -u{}:{} {}/api/copy/{}/{}?to=/{}/{}".format(
                ARTIFACTORY_USER,
                ARTIFACTORY_APIKEY,
                ARTIFACTORY_URL,
                "{}-cache".format(REMOTE_REPO_NAME),
                pkg,
                LOCAL_REPO_NAME,
                pkg
            )
            curl_output = subprocess.run(curl_cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.logger.debug("  curl_output: %s", curl_output)

    def curate(self):
        self.logger.info("Curating PyPi package: %s", self.package_line)
        # Should figure out how to configure pip to pull from remote repo...
        #self._packages_before_install = self._pip_get_current_packages()
        self._install_package() # FIXME: What's the best way to handle failures here?
        #self._packages_after_install = self._pip_get_current_packages()
        # Get the differences
        #self._package_changes = self._compare_packages()
        self._copy_to_local()

### MAIN ###
def main():
    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG
    )

    logging.debug("Environment Prep Starting")
    tmp_payload_json = os.environ['res_curatepypi_payload']
    tmp_packages = get_requirements_from_payload(tmp_payload_json)

    # NOTE: Currently this script uses the '--no-cache' option for pip, which forces download of all packages for each
    #       run of the pip command.  This could be made a bit more efficient by allowing the cache for each run, but
    #       wiping out the cache at the start of the script.

    tmp_pythonpackagepullers = []
    for tmp_pkg in tmp_packages:
        tmp_pythonpackagepullers.append(PythonPackagePuller(tmp_pkg))
    for tmp_puller in tmp_pythonpackagepullers:
        tmp_puller.curate()

    # Report Results


if __name__ == '__main__':
    main()
