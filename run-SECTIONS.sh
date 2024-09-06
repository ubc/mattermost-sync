python ./sync.py \
  -u uid='<ldapcons>' \
  -p '<pwd>' \
  -l ldaps://eldapcons.id.ubc.ca:636 \
  -b ou=SECTIONS,dc=id,dc=ubc,dc=ca \
  -c 'DSCI_V 512 001 2024' \
  -r mattermost.stg.lthub.ubc.ca \
  -t pwd123 \
  -v DEBUG

