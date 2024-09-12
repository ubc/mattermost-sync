#!/bin/bash

# This shell script is used to test the sync.py call.
# Run python sync.py --help for more information

# Note a brief explanation for each flag:
# -u uid='<ldapcons>': LDAP username used for authentication.
# -p '<pwd>': Password associated with the LDAP username.
# -l ldaps://eldapcons.id.ubc.ca:636: URL for the LDAP server, including the protocol (ldaps for secure LDAP) and port (636).
# -b ou=SECTIONS,dc=id,dc=ubc,dc=ca: Base DN (Distinguished Name) for the LDAP search, specifying the starting point of the search in the directory hierarchy.
# -c 'DSCI_V 512 001 2024': Course code or identifier to sync, formatted according to your requirements.
# (optional with additional flag for students) -c '201 100 03 2024 students'
# (optional with additional flag for instructors) -c '201 100 03 2024 instructors'
# -r mattermost.stg.lthub.ubc.ca: URL of the Mattermost server where data will be synced.
# -t <pwd>: Password for Mattermost authentication.
# -v DEBUG: Logging level to output detailed debug information.


python ./sync.py \
  -u uid='<ldapcons>' \
  -p '<pwd>' \
  -l ldaps://eldapcons.id.ubc.ca:636 \
  -b ou=SECTIONS,dc=id,dc=ubc,dc=ca \
  -c 'DSCI_V 512 001 2024' \
  -r mattermost.stg.lthub.ubc.ca \
  -t '<pwd>' \
  -v DEBUG