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
    tmp_images = [] # FIXME: Should this store strings or should there be dictionaries with repo, name, and tag?
    if 'image' in tmp_payload_dict.keys():
        tmp_images.append(str(tmp_payload_dict))
    if 'images' in tmp_payload_dict.keys():
        for tmp_img in tmp_payload_dict['images']:
            tmp_images.append(str(tmp_img))
    logging.debug("  tmp_images: %s", tmp_images)

    # Prep the environment
    logging.debug("Environment Prep Starting")
    tmp_arti_user = os.environ['int_artifactory_user']
    tmp_arti_apikey = os.environ['int_artifactory_apikey']
    tmp_arti_url = os.environ['int_artifactory_url']
    tmp_docker_url = str(tmp_arti_url.split('/')[2])
    tmp_prep_cmd = "docker login -u {} -p {} {}".format(
        tmp_arti_user,
        tmp_arti_apikey,
        tmp_docker_url
    )
    logging.debug("  tmp_prep_cmd: %s", tmp_prep_cmd)
    tmp_prep_output = subprocess.run(tmp_prep_cmd.split(' '), stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    if tmp_prep_output.returncode == 0:
        logging.debug("Successfully logged into docker")
    else:
        logging.warning("Failed to log into docker: %s", tmp_prep_output.stderr)
    logging.info("Environment Prep Complete")

    # Pull each of the images from the remote repo using docker (might switch to podman)
    tmp_pull_successes = []
    tmp_pull_failures = []
    for tmp_img in tmp_images:
        tmp_pull_cmd = "docker pull {}".format(tmp_img)
        logging.debug("  tmp_pull_cmd: %s", tmp_pull_cmd)
        tmp_pull_output = subprocess.run(tmp_pull_output.split(' '), stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        if tmp_pull_output.returncode == 0:
            # Success, add to success list
            logging.info("Successfully pulled '%s'", tmp_img)
            tmp_pull_successes.append(tmp_img)
        else:
            # Failure, add to failure list
            logging.warning("Failed to pull '%s' with error: %s", tmp_img, tmp_pull_output.stderr)
            tmp_pull_failures.append(tmp_img)
    logging.info("Docker Images Pulls Complete")


    # For each of the successes, copy the image to the local repo
    # NOTE: There are at least two versions of docker images.  V1 keeps the layers next
    #       to the manifest file under the tag folder.  V2 keeps the layers under the image
    #       folder and uses a list.manifest.json file under the tag folder.

if __name__ == "__main__":
    main()
