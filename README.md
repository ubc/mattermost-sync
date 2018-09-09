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
  -u uid=BIND_USER \
  -p BIND_PASSWORD \
  -c PSYC_301_902_2018W \
  -r MATTERMOST_URL \
  -t MATTERMOST_ACCESS_TOKEN \
  -b ou=BASE,dc=id,dc=example,dc=com \
  -l ldaps://ldap.server.com:636 \
  -v DEBUG
```

Run `python sync.py --help` for more information

### Course Name

Course name has to follow [ELDAP naming convention](https://confluence.it.ubc.ca/pages/viewpage.action?pageId=105318449).

### Multiple Courses

The script can handle multiple courses by apply `-c/--course` parameter multiple times or use `COURSE_NAMES` environment variable with space separated course name list.
