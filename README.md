# Mattermost Sync

The script sync LDAP groups to Mattermost teams. The script will load
roaster from LDAP, create Mattermost team if needed, create Mattermost
student accounts and enrol them into the team.

## Features

* Handle multiple courses
* Get configuration from environment variables

## Deployment
```
pip install -r requirement.txt
```

## Run
```
python sync.py \
  -u uid='BIND_USER' \
  -p 'BIND_PASSWORD' \
  -l ldaps://ldap.server.com:636 \
  -b ou=BASE,dc=id,dc=example,dc=com \
  -c 'DSCI_V 512 001 2024' \
  -r 'MATTERMOST_URL' \
  -t 'MATTERMOST_ACCESS_TOKEN' \
  -v DEBUG
```

Note a brief explanation for each flag:
* -u uid='BIND_USER': LDAP username used for authentication.
* -p 'BIND_PASSWORD': Password associated with the LDAP username.
* -l ldaps://ldap.server.com:636: URL for the LDAP server, including the protocol (ldaps for secure LDAP) and port (636).
* -b ou=BASE,dc=id,dc=example,dc=com: Base DN (Distinguished Name) for the LDAP search, specifying the starting point of the search in the directory hierarchy.
* -c 'DSCI_V 512 001 2024': Course code or identifier to sync, formatted according to your requirements.
* (optional with additional flag for students) -c '201 100 03 2024 students'
* (optional with additional flag for instructors) -c '201 100 03 2024 instructors'
* -r MATTERMOST_URL: URL of the Mattermost server where data will be synced.
* -t MATTERMOST_ACCESS_TOKEN: Token for Mattermost authentication.
* -v DEBUG: Logging level to output detailed debug information.


Run `python sync.py --help` for more information

### Course Name Spec

The base course name has to follow [ELDAP naming convention](https://confluence.it.ubc.ca/pages/viewpage.action?pageId=105318449).

For the course in UBCO, append 'O' at the end of the course name, e.g. CPSC_110_101_2018WO

For cross listed courses, use plus (`+`) for joining the course and equal (`=`) for the team name, e.g. CPSC_110_101_2018W+CPSC_120_102_2018W=MERGED-CPSC

Mattermost has some restrictions on team name as well: https://docs.mattermost.com/help/getting-started/creating-teams.html#team-name

Here are some examples:

| Course Name Spec | Team Name | Note |
|------------------|-----------|------|
| CPSC_101_201_2018W | CPSC10120118W | UBCV course |
| CPSC_101_301_2018WO | CPSC10130118WO | UBCO course |
| CPSC_101_101_2018W=CUSTOM-TEAM-NAME | CUSTOM-TEAM-NAME | Custom team name with linked the course |
| CPSC_101_101_2018W+CPSC_101_102_2018W=XLISTED-CPSC-101| XLISTED-CPSC-101 | Cross list two CPSC section and custom team name |

### Multiple Courses

The script can handle multiple courses by apply `-c/--course` parameter multiple times or use `COURSE_NAMES` environment variable with space separated course name spec list.
