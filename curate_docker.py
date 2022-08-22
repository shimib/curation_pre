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

SUPPORTED_ARCHITECTURES = ['amd64']

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
        tmp_images.append(str(tmp_payload_dict['image']))
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
        tmp_pull_output = subprocess.run(tmp_pull_cmd.split(' '), stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        if tmp_pull_output.returncode == 0:
            # Success, add to success list
            logging.info("Successfully pulled '%s'", tmp_img)
            tmp_pull_successes.append(tmp_img)
        else:
            # Failure, add to failure list
            logging.warning("Failed to pull '%s' with error: %s", tmp_img, tmp_pull_output.stderr)
            tmp_pull_failures.append(tmp_img)
    logging.info("Docker Images Pulls Complete")


    # For each of the pull successes, copy the image to the local repo
    # NOTE: There are at least two versions of docker images.  V1 keeps the layers next
    #       to the manifest file under the tag folder.  V2 keeps the layers under the image
    #       folder and uses a list.manifest.json file under the tag folder.
    # NOTE: This assumes that any "library" images contain "library" in the image name
    # Check if image is V1 or V2
    #   - Attempt to pull tag/list.manifest.json.  If successful, V2 image.
    #   - Attempt to pull tag/manifest.json.  If successful, V1 image.
    #   - Else fail.
    tmp_images_v1 = []
    tmp_images_v2 = []
    for tmp_img in tmp_pull_successes:
        tmp_image_tag = tmp_img.split(':')
        logging.debug("  tmp_image_tag: %s", tmp_image_tag)
        tmp_image_split = tmp_image_tag[0].split('/')
        logging.debug("  tmp_image_split: %s", tmp_image_split)
        tmp_image_arti_name = "{}/{}/{}/{}".format(
            tmp_image_split[1],
            tmp_image_split[2],
            tmp_image_split[3],
            tmp_image_tag[1]
        )
        tmp_curl1_cmd = "curl -f -u{}:{} {}/{}/list.manifest.json".format(
            tmp_arti_user,
            tmp_arti_apikey,
            tmp_arti_url,
            tmp_image_arti_name
        )
        tmp_curl1_output = subprocess.run(tmp_curl1_cmd.split(' '), stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        if tmp_curl1_output.returncode == 0:
            # Succeeded in pulling the V2 type image manifest.
            logging.debug("  tmp_curl1_output: %s", tmp_curl1_output)
            tmp_mani_dict = json.loads(tmp_curl1_output.stdout.decode())
            tmp_images_v2.append({
                'image': tmp_img,
                'manifests': tmp_mani_dict['manifests']
            })
        else:
            # Failure in pulling V2, so try V1
            pass
        # curate_image="$(
        #     curl -u${int_artifactory_user}:${int_artifactory_apikey} ${int_artifactory_url}/${artPath}/list.manifest.json |
        #     jq -r '.manifests[] | select(.platform.architecture | contains("amd64")) |  "sha256__" + (.digest | sub("^sha256:"; "")) '
        # )"; fi

    # V1:
        # Get and parse manifest.json
        # Ensure the tag directory exists in the local repository.
        # Copy each of the layers to the local repository.
        # Copy the manifest.json to the local repository.

    # V2:
        # Parse list.manifest.json
        # For each layer:
            # Ensure the layer directory exists in the local repository.
            # Copy each of the layer components to the local repository.
            # Copy the manifest.json for the layer to the local repository.
        # Ensure the tag directory exists in the local repository.
        # Copy the list.manifest.json to the local repository.
    for tmp_img in tmp_images_v2:
        tmp_layers = tmp_img['manifests']
        logging.debug("  tmp_layers: %s", tmp_layers)
        for tmp_layer in tmp_layers:
            if tmp_layer['platform']['architecture'] in SUPPORTED_ARCHITECTURES:
                tmp_layer_name = "__".join(tmp_layer['digest'].split(':'))
                logging.debug("  tmp_layer_name: %s", tmp_layer_name)

                tmp_image_tag = tmp_img['image'].split(':')
                logging.debug("  tmp_image_tag: %s", tmp_image_tag)
                tmp_image_split = tmp_image_tag[0].split('/')
                logging.debug("  tmp_image_split: %s", tmp_image_split)
                tmp_layer_arti_name = "{}/{}/{}/{}".format(
                    tmp_image_split[1],
                    tmp_image_split[2],
                    tmp_image_split[3],
                    tmp_layer_name
                )
                tmp_curl2_cmd = "curl -f -u{}:{} {}/{}/manifest.json".format(
                    tmp_arti_user,
                    tmp_arti_apikey,
                    tmp_arti_url,
                    tmp_layer_arti_name
                )
                tmp_curl2_output = subprocess.run(tmp_curl2_cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if tmp_curl2_output.returncode == 0:
                    # Succeeded in pulling the V2 type image manifest.
                    logging.debug("  tmp_curl2_output: %s", tmp_curl2_output)
                    tmp_layer_mani_dict = json.loads(tmp_curl2_output.stdout.decode())
                    # tmp_images_v2.append({
                    #     'image': tmp_img,
                    #     'manifest': tmp_mani_dist
                    # })
                else:
                    pass


    # Report Results

if __name__ == "__main__":
    main()
