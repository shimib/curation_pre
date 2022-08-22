#!/usr/bin/env python3

### IMPORTS ###
import base64
import json
import logging
import os
import subprocess
import sys

### GLOBALS ###
REMOTE_REPO_NAME = "demo-docker"
LOCAL_REPO_NAME = "demo-docker-local"

### FUNCTIONS ###

### CLASSES ###

### MAIN ###
def main():
    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG
    )

    # Get the list of docker images from the payload stored in an environment variable
    tmp_payload_json = os.environ['res_curatedocker_payload']
    logging.debug("  tmp_payload_json: %s", tmp_payload_json)
    tmp_payload_dict = json.loads(tmp_payload_json)
    logging.debug("  tmp_payload_dict: %s", tmp_payload_dict)

    # Prep the environment
    tmp_arti_user = os.environ['int_artifactory_user']
    tmp_arti_apikey = os.environ['int_artifactory_apikey']
    tmp_arti_url = os.environ['int_artifactory_url']
    tmp_docker_url = str(tmp_arti_url.split())
    tmp_prep_cmd = "docker login -u {} -p {} {}".format(
        tmp_arti_user,
        tmp_arti_apikey,
        tmp_docker_url
    )
    logging.debug("  tmp_prep_cmd: %s", tmp_prep_cmd)

    # Pull each of the images from the remote repo using docker (might switch to podman)

    # For each of the successes, copy the image to the local repo
    # NOTE: There are at least two versions of docker images.  V1 keeps the layers next
    #       to the manifest file under the tag folder.  V2 keeps the layers under the image
    #       folder and uses a list.manifest.json file under the tag folder.

if __name__ == "__main__":
    main()
