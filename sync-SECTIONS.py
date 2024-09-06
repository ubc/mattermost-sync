import click
import click_log
import logging
from requests import HTTPError

from mattermostsync import Sync, CourseNotFound, parse_course

logger = logging.getLogger('lthub.mattermost')
click_log.basic_config(logger)


@click.command()
@click_log.simple_verbosity_option(logger)
@click.option('-l', '--ldap', help='LDAP URI', envvar='LDAP_URI', default='ldaps://localhost:636', show_default=True)
@click.option('-u', '--bind', help='LDAP bind user', envvar='LDAP_BIND_USER', required=True)
@click.option(
    '-p', '--password', help='LDAP bind password', envvar='LDAP_BIND_PASSWORD',
    required=True, prompt=True, hide_input=True
)
@click.option('-b', '--base', help='LDAP search base', envvar='LDAP_SEARCH_BASE', show_default=True)
@click.option(
    '-c', '--courses', help='Course names spec, can be specified multiple times',
    envvar='COURSE_NAMES', multiple=True, required=True
)
@click.option('-r', '--url', help='Mattermost URL', envvar='MM_URL', required=True)
@click.option('-o', '--port', help='Mattermost port', envvar='MM_PORT', default=443, show_default=True)
@click.option('-t', '--token', help='Mattermost token', envvar='MM_TOKEN', required=True)
@click.option(
    '-s', '--scheme', help='Mattermost scheme', envvar='MM_SCHEME',
    default='https', type=click.Choice(['http', 'https']), show_default=True
)
def sync(ldap, bind, password, base, courses, url, port, token, scheme):
    """Sync class roaster from LDAP to Mattermost
    """
    mm = Sync({
        'url': url,
        'token': token,
        'port': port,
        'scheme': scheme,
        'debug': logger.getEffectiveLevel() <= logging.DEBUG,
        'ldap_uri': ldap,
        'bind_user': bind,
        'bind_password':  password
    })
    mm.driver.login()

    for course in courses:
        source_courses, team_name = parse_course(course)
        logger.info('SSSSSSyncing course {} to team {}.'.format(source_courses, team_name))

        logger.info('XXXX:{}'.format(len(source_courses)))

        try:
            course_members = []
            for c in source_courses:
                logger.info('XXXX:{} :: {}'.format(base,c))
                course_members.extend(mm.get_member_from_ldap(base, *c))
        except CourseNotFound as e:
            logger.warning(e)
            continue

        try:
            #team_name = 'TUE TESTTWO2'
            team_name = team_name.replace(" ", "-")
            print("XXXX: CHECK TEAM NAME::" + team_name )
            team = mm.get_team_by_name(team_name)
            ##team = mm.get_team_by_name("Test111")
            if team:
                logger.info('Team {} already exists.'.format(team_name))
            else:
                team = mm.create_team(team_name)
                logger.info('Team {} is created.'.format(team_name))
            existing_users, failed_users = mm.create_users(course_members)

            # check if the users are already in the team
            members = []
            for i in range(1000):
                m = mm.get_team_members(team['id'], {'page': i, 'per_page': 60})
                if m:
                    members.extend(m)
                    continue

                if len(m) < 60:
                    break
            member_ids = [m['user_id'] for m in members]
            users_to_add = []
            for u in existing_users:
                if u['id'] not in member_ids:
                    users_to_add.append(u)

            # add the missing ones
            if users_to_add:
                mm.add_users_to_team(users_to_add, team['id'])
            else:
                logger.info('No new users to add.')
        except HTTPError as e:
            logging.error('Failed to sync team {}: {}'.format(team_name, e.args))
            continue
        logger.info('Finished to sync course {}.'.format(course))


if __name__ == "__main__":
    sync()
