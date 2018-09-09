import hashlib
import json
import ldap
import logging
import re
from mattermostdriver import Driver
from mattermostdriver.exceptions import ResourceNotFound
from requests import HTTPError


def to_mm_team_name(raw_name, campus):
    team_name = re.sub('20(1[0-9])', r'\1', raw_name.replace('_', ''))
    if campus == 'UBCO':
        team_name = team_name + 'O'
    return team_name


def get_dummy_email(username):
    return hashlib.sha1(username.encode('utf-8')).hexdigest()[:10] + '@noemail.ubc.ca'


class CourseNotFound(RuntimeError):
    pass


class Sync:
    def __init__(self, config):
        self.logger = logging.getLogger('lthub.mattermost.sync')
        self.config = config
        self.driver = Driver(config)

    def get_member_from_ldap(self, server, bind, password, base, course, campus='UBC'):
        ldap_server = ldap.initialize(server)
        ldap_server.simple_bind_s(bind, password)
        ldap_filter = '(&(cn={})(ou:dn:={}))'.format(course, campus)
        r = ldap_server.search_s(base, ldap.SCOPE_SUBTREE, ldap_filter, ['uniqueMember'])

        if not r:
            raise CourseNotFound('Course {} at {} doesn\'t exist in ELDAP.'.format(course, campus))

        members = []
        member_emails = []
        for dn, entry in r:
            self.logger.info('Processing {}'.format(dn))
            member_filter = "(|({}))".format(b')('.join(entry['uniqueMember']).decode("utf-8")).replace(
                ',ou=PEOPLE,ou=IDM,dc=id,dc=ubc,dc=ca', '')
            result = ldap_server.search_s(
                'ou=PEOPLE,ou=IDM,dc=id,dc=ubc,dc=ca',
                ldap.SCOPE_SUBTREE, member_filter,
                # ['cn', 'sn', 'ubcEduCwlPUID', 'uid', 'displayName', 'givenName', 'mail']
                ['sn', 'ubcEduCwlPUID', 'uid', 'givenName', 'mail']
            )
            for member_dn, member in result:
                m = {
                    # 'email': member['mail'][0].decode('utf-8').replace('@', 'noemail@') if 'mail' in member else '',
                    'email': member['mail'][0].decode('utf-8') if 'mail' in member else '',
                    'username': member['uid'][0].decode('utf-8'),
                    'first_name': member['givenName'][0].decode('utf-8'),
                    'last_name': member['sn'][0].decode('utf-8'),
                    # 'nickname': member['displayName'][0].decode('utf-8'),
                    # 'cn': member['cn'][0].decode('utf-8'),
                    'props': {
                        'puid': member['ubcEduCwlPUID'][0].decode('utf-8')
                    }
                }
                if m['email'] in member_emails:
                    self.logger.warning('Found duplicate email, skipping: {}'.format(json.dumps(m)))
                    continue
                members.append(m)
                member_emails.append(m['email'])

        self.logger.info('Get {} student in course {} {}'.format(len(members), course, campus))
        self.logger.debug('Students:' + str(members))
        return members

    def create_team(self, team_name):
        try:
            team = self.driver.teams.get_team_by_name(team_name)
            self.logger.info('Team {} already exists.'.format(team_name))
        except ResourceNotFound:
            # no team is found under team_name, create a new one
            team = self.driver.teams.create_team({
                'name': team_name.lower(),
                'display_name': team_name,
                'type': 'I'
            })
            self.logger.info('Created team {}.'.format(team_name))

        return team

    def create_users(self, users):
        usernames = [x['username'] for x in users]
        existing_users = []
        existing_usernames = []
        failed_users = []
        # alphabet = string.ascii_letters + string.digits

        if usernames:
            existing_users = self.driver.users.get_users_by_usernames(usernames)
            existing_usernames = [x['username'] for x in existing_users]
            self.logger.debug('Existing users:' + str(existing_usernames))

        for i in users:
            if i['username'] not in existing_usernames:
                # no password field allowed when creating ldap user
                # i['password'] = ''.join(secrets.choice(alphabet) for i in range(20))
                # auth_service and auth_data are undocumented properties from user.create_user API
                # they are used in bulk load though
                # https://docs.mattermost.com/deployment/bulk-loading-data-format.html#data-format
                i['auth_service'] = 'ldap'
                i['auth_data'] = i['username']
                if not i['email']:
                    i['email'] = get_dummy_email(i['username'])
                    self.logger.warning(
                        'No email found for {}. Created a dummy one: {}'.format(i['username'], i['email']))
                try:
                    user = self.driver.users.create_user(i)
                    existing_users.append(user)
                except HTTPError as e:
                    self.logger.warning('Failed to create user {}: {}'.format(json.dumps(i), e))
                    failed_users.append(i)

        return existing_users, failed_users

    def get_team_members(self, team_id, params=None):
        return self.driver.teams.get_team_members(team_id, params)

    def add_users_to_team(self, users, team_id):
        """
        Add users to team in bulk
        :param users: list of users
        :param team_id: team id
        """
        self.logger.debug('Adding {} user to team id {}.'.format(len(users), team_id))
        users_to_add = []
        for u in users:
            users_to_add.append({
                'team_id': team_id,
                'user_id': u['id'],
                'roles': 'team_user'
            })

        # split into chunks
        chunks = [users_to_add[i:i + 10] for i in range(0, len(users_to_add), 10)]

        for c in chunks:
            self.driver.teams.add_multiple_users_to_team(team_id, c)
