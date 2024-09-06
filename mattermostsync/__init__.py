import hashlib
import json
import ldap
import logging
import re

from ldap.controls import SimplePagedResultsControl
from mattermostdriver import Driver
from mattermostdriver.exceptions import ResourceNotFound, InvalidOrMissingParameters
from requests import HTTPError

## SECTIONS ##############

LDAP_USER_SEARCH_BASE = 'ou=PEOPLE,ou=IDM,dc=id,dc=ubc,dc=ca'
# ['cn', 'sn', 'ubcEduCwlPUID', 'uid', 'displayName', 'givenName', 'mail']
LDAP_ATTRIBUTES = ('sn', 'ubcEduCwlPUID', 'uid', 'givenName', 'mail')


def to_mm_team_name(raw_name):
    return re.sub('20(1[0-9])', r'\1', raw_name.replace('_', ''))


def split_campus(course):
    print("XXXXX split_campus:::" + course)
    ##return (course[:-1], 'UBCO') if course.endswith('O') or course.endswith('o') else (course, 'UBC')
    return (course[:-1], 'O') if course.endswith('O') or course.endswith('o') else (course, 'V')


def get_dummy_email(username):
    return hashlib.sha1(username.encode('utf-8')).hexdigest()[:10] + '@noemail.ubc.ca'


class CourseNotFound(RuntimeError):
    pass


def parse_course(course):
    """Parse course names
    :param course: raw course string
    :return: course list and target team name
    """
    # check if the course name is xlisted
    xlisted = course.split('=')
    if len(xlisted) == 2:
        courses = [split_campus(c) for c in xlisted[0].split('+')]
        target_team = xlisted[1]
        if len(target_team) < 2 or len(target_team) > 15:
            raise ValueError('Invalid team name {}. Team name must be 2–15 characters in length.')
    elif len(xlisted) > 2:
        raise ValueError('Invalid course name {}'.format(course))
    else:
        target_team = to_mm_team_name(course)
        courses = [split_campus(course)]

    return courses, target_team


class Sync:
    def __init__(self, config):
        self.logger = logging.getLogger('lthub.mattermost.sync')
        self.config = config
        self.driver = Driver({k: config[k] for k in config.keys() & Driver.default_options.keys()})

    def get_member_from_ldap(self, base, course, campus='V', attributes=LDAP_ATTRIBUTES):
        print("XXXXXX:get_member_from_ldap")
        ldap_server = ldap.initialize(self.config['ldap_uri'])
        print("XXXXXX:get_member_from_ldap:ldap_server:" + self.config['ldap_uri'])
        print("XXXXXX:SIMPLE_BIND:ldap_server:" + self.config['bind_user'] + ":::" + self.config['bind_password'])

        # Split the course string into its components
        parts = course.split()

        # Assign the components to respective variables
        CourseSubjectCode = parts[0]  # 'ELEC_A'
        CourseNumber = parts[1]  # '201'
        CourseSectionNumber = parts[2]
        CourseAcademicYear = parts[3] # 2024
        courseCN = "students"

        # Create the LDAP filter using the new variables
        ldap_filter = '(&(cn={})(ubcAcademicYear={})(ubcCourseSubjectCode={})(ubcCourseNumber={})(ubcCourseSectionNumber={})(ou:dn:={}))'.format(
            courseCN, CourseAcademicYear, CourseSubjectCode, CourseNumber, CourseSectionNumber, campus
        )
        #ldap_filter = '(&(cn={})(ou:dn:={}))'.format(course, campus)
        print("XXXXXXX:ldap_filter:" + ldap_filter)
        print("XXXXXXX:bind_user:" + self.config['bind_user'])

        ldap_server.simple_bind_s(self.config['bind_user'], self.config['bind_password'])
        ##ldap_filter = '(&(cn={})(ou:dn:={}))'.format(course, campus)
        print("XXXXX--X:BASE:" + base)
        print("XXXXX--X:ldap.SCOPE_SUBTREE:" + str(ldap.SCOPE_SUBTREE))
        print("XXXXX--X:ldap_filter:" + str(ldap_filter))

        ##r = ldap_server.search_s(base, ldap.SCOPE_SUBTREE, ldap_filter, ['uniqueMember'])
        req_ctrl = SimplePagedResultsControl(criticality=True, size=1, cookie='')
        r = ldap_server.search_ext_s( base, ldap.SCOPE_SUBTREE, ldap_filter, ['uniqueMember'], serverctrls=[req_ctrl])

        if not r:
            raise CourseNotFound('Course {} at {} doesn\'t exist in ELDAP.'.format(course, campus))

        members = []
        member_emails = []
        for dn, entry in r:
            self.logger.info('Processing {}'.format(dn))
            if (len(entry) == 0):
                continue
            usernames = [x.decode('utf-8').replace(',' + LDAP_USER_SEARCH_BASE, '').replace('uid=', '')
                         for x in entry['uniqueMember']]
            users = self.get_users_from_ldap(usernames, ldap_server=ldap_server, attributes=attributes)
            # remove members with duplicate email
            for m in users:
                if m['email'] in member_emails:
                    self.logger.warning('Found duplicate email, skipping: {}'.format(json.dumps(m)))
                    continue
                members.append(m)
                member_emails.append(m['email'])

        self.logger.info('Get {} student in course {} {}'.format(len(members), course, campus))
        self.logger.debug('Students:' + str(members))
        return members

    def get_users_from_ldap(self, usernames, ldap_server=None, attributes=LDAP_ATTRIBUTES):
        if not ldap_server:
            ldap_server = ldap.initialize(self.config['ldap_uri'])
            ldap_server.simple_bind_s(self.config['bind_user'], self.config['bind_password'])

        if not isinstance(usernames, list):
            usernames = [usernames]

        user_filter = "(|(uid={}))".format(')(uid='.join(usernames))

        result = ldap_server.search_s(
            LDAP_USER_SEARCH_BASE,
            ldap.SCOPE_SUBTREE, user_filter,
            attributes
        )

        users = []
        for member_dn, member in result:
            m = {
                # 'email': member['mail'][0].decode('utf-8').replace('@', 'noemail@') if 'mail' in member else '',
                'email'     : member['mail'][0].decode('utf-8') if 'mail' in member else '',
                'username'  : member['uid'][0].decode('utf-8'),
                'first_name': member['givenName'][0].decode('utf-8'),
                'last_name' : member['sn'][0].decode('utf-8'),
                # 'nickname': member['displayName'][0].decode('utf-8'),
                # 'cn': member['cn'][0].decode('utf-8'),
                'props'     : {
                    'puid': member['ubcEduCwlPUID'][0].decode('utf-8')
                }
            }
            if 'ubcEduStudentNumber' in member:
                m['props']['student_number'] = member['ubcEduStudentNumber'][0].decode('utf-8')
            users.append(m)
        return users

    def get_team_by_name(self, team_name):
        try:
            team = self.driver.teams.get_team_by_name(team_name)
        except ResourceNotFound:
            return None
        except InvalidOrMissingParameters:
            raise ValueError('Invalid team name. Please see Mattermost team name rules'
                             ' (https://docs.mattermost.com/help/getting-started/creating-teams.html#team-name).\n'
                             'Hint: did you include underscore("-") in the team name?')
        return team

    def create_team(self, team_name, display_name='', team_type='I'):

        print("XXXX-CREATE-MATTERMOST:TEAM::" + team_name)

        if not display_name:
            display_name = team_name

        try:
            # no team is found under team_name, create a new one
            team = self.driver.teams.create_team({
                'name': team_name.lower(),
                'display_name': display_name,
                'type': team_type
            })
            self.logger.info('Created team {}.'.format(team_name))
        except InvalidOrMissingParameters:
            raise ValueError('Invalid team name. Please see Mattermost team name rules'
                             '(https://docs.mattermost.com/help/getting-started/creating-teams.html#team-name).')

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

    def add_users_to_team(self, users, team_id, roles='team_user'):
        """
        Add users to team in bulk
        :param users: list of users
        :param team_id: team id
        :param roles: string for role info, e.g. 'team_member', 'team_admin'
        """
        self.logger.debug('Adding {} user to team id {} as {}.'.format(len(users), team_id, roles))
        users_to_add = []
        for u in users:
            users_to_add.append({
                'team_id': team_id,
                'user_id': u['id'],
                'roles': roles
            })

        # split into chunks
        chunks = [users_to_add[i:i + 10] for i in range(0, len(users_to_add), 10)]

        for c in chunks:
            self.driver.teams.add_multiple_users_to_team(team_id, c)
