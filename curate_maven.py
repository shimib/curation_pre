#!/usr/bin/env python3

### IMPORTS ###
import base64
import json
import logging
import os
import subprocess
import sys

### GLOBALS ###
REMOTE_REPO_NAME = "demo-maven"
LOCAL_REPO_NAME = "demo-maven-local"

### FUNCTIONS ###
def format_jar_line(input_line):
    logging.debug("  input_line: %s", input_line)
    # NOTE: Here's an example of the line processing here.
    #   tmp_line: [INFO]    org.apache.tinkerpop:gremlin-shaded:jar:3.5.3:compile
    #   ':jar:' found
    #   input_line: org.apache.tinkerpop:gremlin-shaded:jar:3.5.3:compile
    #     tmp_split: #5 - ['org.apache.tinkerpop', 'gremlin-shaded', 'jar', '3.5.3', 'compile']
    #     tmp_path: org/apache/tinkerpop
    #   output_line: org/apache/tinkerpop/gremlin-shaded/3.5.3/gremlin-shaded-3.5.3.jar
    tmp_split = input_line.split(':')
    logging.debug("    tmp_split: #%d - %s", len(tmp_split), tmp_split)
    tmp_path = "/".join(tmp_split[0].split('.'))
    logging.debug("    tmp_path: %s", tmp_path)
    tmp_name = "{}-{}.jar".format(tmp_split[1], tmp_split[-2])
    # NOTE: Check for the architecture classifier.  This should be a more complete processor for the lines.
    if len(tmp_split) == 6:
        tmp_name = "{}-{}-{}.jar".format(tmp_split[1], tmp_split[-2], tmp_split[-3])
    tmp_full_path = "{}/{}/{}/{}".format(tmp_path, tmp_split[1], tmp_split[-2], tmp_name)
    logging.debug("  output_line: %s", tmp_full_path)
    return tmp_full_path

### CLASSES ###

### MAIN ###
def main():
    # Set up logging
    logging.basicConfig(
        format = "%(asctime)s:%(levelname)s:%(name)s:%(funcName)s: %(message)s",
        level = logging.DEBUG
    )

    # Get the pom.xml from the payload stored in an environment variable and write it to a pom.xml file
    tmp_payload_json = os.environ['res_curatemaven_payload']
    logging.debug("  tmp_payload_json: %s", tmp_payload_json)
    tmp_payload_dict = json.loads(tmp_payload_json)
    logging.debug("  tmp_payload_dict: %s", tmp_payload_dict)
    tmp_pomxml_base64 = tmp_payload_dict['pomdata']
    logging.debug("  tmp_pomxml_base64: %s", tmp_pomxml_base64)
    tmp_pomxml_str = base64.b64decode(tmp_pomxml_base64)
    logging.debug("  tmp_pomxml_str: %s", tmp_pomxml_str)
    with open('pom.xml', 'w', encoding='utf-8') as tmp_pomxml_file:
        tmp_pomxml_file.write(tmp_pomxml_str.decode())
    logging.info("pom.xml file written")

    # Run 'mvn dependency:list' and process the output
    tmp_jar_lines = []
    tmp_mvn_output = subprocess.run('mvn -B dependency:list'.split(' '), stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    logging.debug("tmp_mvn_output: %s", tmp_mvn_output)
    tmp_mvn_str = tmp_mvn_output.stdout.decode()
    tmp_mvn_list = tmp_mvn_str.split('\n')
    logging.debug("tmp_mvn_list: %s", tmp_mvn_list)
    for tmp_line in tmp_mvn_list:
        logging.debug("  tmp_line: %s", tmp_line)
        if (':jar:' in tmp_line) and ('has been relocated' not in tmp_line):
            logging.debug("  ':jar:' found")
            # NOTE: This should be expanded to handle 'ear' files and 'war' files.
            # NOTE: This is crude parsing of the lines returned from maven
            tmp_jar_lines.append(format_jar_line(tmp_line.replace('[INFO]    ', '')))
    logging.info("dependencies processed")

    # Make http/curl requests to artifactory to curate each jar file
    tmp_jar_failures = []
    tmp_jar_successes = []
    # NOTE: Using a shortcut here by shelling out to call CURL commands.  This should be updated to use urllib,
    #       or better yet, a library like requests
    for tmp_jar_line in tmp_jar_lines:
        logging.debug("  tmp_jar_line: %s", tmp_jar_line)
        tmp_curl_cmd = "curl -f -s -S -u{}:{} {}/{}/{}".format(
            os.environ['int_artifactory_user'],
            os.environ['int_artifactory_apikey'],
            os.environ['int_artifactory_url'],
            str(REMOTE_REPO_NAME),
            tmp_jar_line
        )
        logging.debug("  tmp_curl_cmd: %s", tmp_curl_cmd)
        tmp_curl_output = subprocess.run(tmp_curl_cmd.split(' '), stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        if tmp_curl_output.returncode == 0:
            # Success, add to success list
            logging.info("Successfully pulled '%s'", tmp_jar_line)
            tmp_jar_successes.append(tmp_jar_line)
        else:
            # Failure, add to failure list
            logging.warning("Failed to pull '%s' with error: %s", tmp_jar_line, tmp_curl_output.stderr)
            tmp_jar_failures.append(tmp_jar_line)
    logging.info("requests completed")

    # Copy successfully pulled artifacts to the local (curated) repo.
    tmp_copy_successes = []
    tmp_copy_failures = []
    for tmp_jar_line in tmp_jar_successes:
        logging.debug("  tmp_jar_line: %s", tmp_jar_line)
        # curl -XPOST -u${user}:${apikey} ${int_artifactory_url}/api/copy/${artBase}/${curate_image}?to=/shimi-curated/${artImageBase}/${curate_image}
        # Make sure the directory exists.
        # FIXME: Is this touching the directories needed?
        #        Should we check for pre-existing versions?
        #        Should we just overwrite the local repo files?
        #        Can we detect copy errors due to the file already existing?
        tmp_curl1_cmd = "curl -f -s -S -XPUT -u{}:{} {}/{}/{}".format(
            os.environ['int_artifactory_user'],
            os.environ['int_artifactory_apikey'],
            os.environ['int_artifactory_url'],
            str(LOCAL_REPO_NAME),
            tmp_jar_line
        )
        logging.debug("  tmp_curl1_cmd: %s", tmp_curl1_cmd)
        tmp_curl1_output = subprocess.run(tmp_curl1_cmd.split(' '), stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        if tmp_curl1_output.returncode == 0:
            # Success, add to success list
            logging.info("Successfully touched the directory '%s'", tmp_jar_line)
        else:
            # Failure
            logging.warning("Failed to touch the directory '%s' with error: %s", tmp_jar_line, tmp_curl1_output.stderr)
            tmp_copy_failures.append(tmp_jar_line)
            continue  # Skip to the next cycle of the for loop
        # Copy the JAR file
        tmp_curl2_cmd = "curl -f -s -S -XPOST -u{}:{} {}/api/copy/{}/{}?to={}/{}".format(
            os.environ['int_artifactory_user'],
            os.environ['int_artifactory_apikey'],
            os.environ['int_artifactory_url'],
            str(REMOTE_REPO_NAME),
            tmp_jar_line,
            str(LOCAL_REPO_NAME),
            tmp_jar_line
        )
        logging.debug("  tmp_curl2_cmd: %s", tmp_curl2_cmd)
        tmp_curl2_output = subprocess.run(tmp_curl2_cmd.split(' '), stdout = subprocess.PIPE, stderr = subprocess.PIPE)
        if tmp_curl2_output.returncode == 0:
            # Success, add to success list
            logging.info("Successfully copied '%s'", tmp_jar_line)
            tmp_copy_successes.append(tmp_jar_line)
        else:
            # Failure
            logging.warning("Failed to copy '%s' with error: %s", tmp_jar_line, tmp_curl2_output.stderr)
            tmp_copy_failures.append(tmp_jar_line)
    logging.info("copies completed")

    # Write failure list to a file
    with open('curation_pull_failures.txt', 'w', encoding='utf-8') as tmp_fail_file:
        for tmp_line in tmp_jar_failures:
            tmp_fail_file.write("{}\n".format(tmp_line))
    with open('curation_copy_failures.txt', 'w', encoding='utf-8') as tmp_fail_file:
        for tmp_line in tmp_copy_failures:
            tmp_fail_file.write("{}\n".format(tmp_line))
    logging.debug("failure files written")

    # Print a summary of the results and exit with a code if there are failures
    logging.info("The following artifacts have been successfully curated:")
    for tmp_line in tmp_copy_successes:
        logging.info("  %s", tmp_line)
    if len(tmp_jar_failures) > 0 or len(tmp_copy_failures) > 0:
        logging.warning("The following artifacts require more attention:")
        for tmp_line in tmp_jar_failures:
            logging.warning("  (pull) %s", tmp_line)
        for tmp_line in tmp_copy_failures:
            logging.warning("  (copy) %s", tmp_line)

if __name__ == "__main__":
    main()
