#!/usr/bin/python3

import subprocess
import selectors
import argparse
import logging
import shutil
import time
import yaml
import sys
import os
import io

infrastructure_repo = "https://github.com/adrianreber/ohpc-infrastructure.git"
working_directory = "ohpc-infrastructure/ansible/roles/test/files/"

logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)

def run_command(command):
    logging.info("About to run command %s" % ' '.join(command))
    process = subprocess.Popen(
        command,
        bufsize=1,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )

    buf = io.StringIO()

    def handle_output(stream, mask):
        line = stream.readline()
        buf.write(line)
        sys.stdout.write(line)

    selector = selectors.DefaultSelector()
    selector.register(
        process.stdout,
        selectors.EVENT_READ,
        handle_output,
    )

    while process.poll() is None:
        events = selector.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)

    return_code = process.wait()
    selector.close()

    output = buf.getvalue()
    buf.close()

    return ((return_code == 0), output)


def loop_command(command, max_attempts=5):
    output = None
    attempt_counter = 0

    while True:
        attempt_counter += 1

        try:
            (success, output) = run_command(command)
            if success:
                return (True, output)
        except Exception as e:
            logging.error("Exception: %s" % e)

        if attempt_counter >= abs(max_attempts):
            return (False, output)

        logging.info("Retrying attempt '%i'" % attempt_counter)
        time.sleep(attempt_counter)

# Load the information which tests should be run.
# This is done before changing the directory. If the requested
# tests are actually supported will be checked later.
with open("run-tests.yaml") as run_tests:
    try:
        requested = yaml.safe_load(run_tests)
    except yaml.YAMLError:
        logging.error("Reading requested test configuration failed")
        sys.exit(1)

git_checkout_command = [
        'git',
        'clone',
        infrastructure_repo,
        ]

success, _ = loop_command(git_checkout_command)
if not success:
    logging.error("Checking out infrastructure repository failed")
    sys.exit(1)

os.chdir(working_directory)

# This is the configuration what is actually supported and in another repository
with open("run-tests-config.yaml") as test_config:
    try:
        supported = yaml.safe_load(test_config)
    except yaml.YAMLError:
        logging.error("Reading supported test configuration failed")
        sys.exit(1)

not_supported = False

for release in requested['releases']:
    if release not in supported['supported_releases']:
        logging.error(
            "Requested version (%s) not in list of supported releases (%s)",
            release,
            supported['supported_releases'],
        )
        not_supported = True

for o_s in requested['os']:
    if o_s not in supported['supported_os']:
        logging.error(
            "Requested os (%s) not in list of supported os (%s)",
            o_s,
            supported['supported_os'],
        )
        not_supported = True

for arch in requested['arches']:
    if arch not in supported['supported_arches']:
        logging.error(
            "Requested arch (%s) not in list of supported arches (%s)",
            arch,
            supported['supported_arches'],
        )
        not_supported = True

for repository in requested['repositories']:
    if repository not in supported['supported_repositories']:
        logging.error(
            "Requested repository (%s) not in list of supported repositories (%s)",
            repository,
            supported['supported_repositories'],
        )
        not_supported = True

if not_supported:
    sys.exit(1)

hostname = os.uname()[1]

if len(hostname) == 0:
    logging.error("Unable to determine hostname")
    sys.exit(1)

supported_host_found = False

for arch in requested['arches']:
    for hosts in supported['supported_arches'][arch]:
        if hostname in hosts:
            supported_host_found = True
            break
    if supported_host_found:
        break

if not supported_host_found:
    logging.info("This host (%s) does not support any of the requested test architectures (%s)" % (hostname, requested['arches']))
    sys.exit(0)

failed = []
test_success = []

for o_s in requested['os']:
    for repository in supported['supported_repositories']:
        for release in requested['releases']:
            test_command = [
                "./run-ci.sh",
                o_s,
                str(release),
                repository,
                ]
            success, _ = run_command(test_command)
            if success:
                test_success.append(test_command)
            else:
                logging.error("Running '%s' failed" % test_command)
                failed.append(test_command)

for success in test_success:
    logging.info("----> %s" % success)

if len(failed) > 0:
    logging.error("--> %d tests failed" % len(failed))
    for fail in failed:
        logging.info("----> %s failed" % fail)

    logging.error("ERROR")
    sys.exit(1)

logging.info("All tests finished successfully")
sys.exit(0)
