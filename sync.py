import click
import click_log
import logging
from requests import HTTPError

from mattermostsync import Sync, to_mm_team_name, CourseNotFound

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
    '-c', '--courses', help='Course names, can be specified multiple times',
    envvar='COURSE_NAMES', multiple=True, required=True
)
@click.option('-m', '--campus', help='Campus', envvar='CAMPUS', default='UBC', show_default=True)
@click.option('-r', '--url', help='Mattermost URL', envvar='MM_URL', required=True)
@click.option('-o', '--port', help='Mattermost port', envvar='MM_PORT', default=443, show_default=True)
@click.option('-t', '--token', help='Mattermost token', envvar='MM_TOKEN', required=True)
@click.option(
    '-s', '--scheme', help='Mattermost scheme', envvar='MM_SCHEME',
    default='https', type=click.Choice(['http', 'https']), show_default=True
)
def sync(ldap, bind, password, base, courses, campus, url, port, token, scheme):
    """Sync class roaster from LDAP to Mattermost
    """
    logger.debug("LDAP Server: {}@{}/{}".format(bind, ldap, base))
    # logger.debug("LDAP Pass: {}".format(password))
    logger.debug("Course Name: {}".format(courses))
    logger.debug("Campus: {}".format(campus))

    mm = Sync({
        'url': url,
        'token': token,
        'port': port,
        'scheme': scheme,
        'debug': logger.getEffectiveLevel() <= logging.DEBUG
    })
    mm.driver.login()

    for course in courses:
        logger.info('Syncing course {}.'.format(course))
        try:
            members = mm.get_member_from_ldap(ldap, bind, password, base, course, campus)
        except CourseNotFound as e:
            logger.warning(e)
            continue

        team_name = to_mm_team_name(course, campus)
        try:
            team = mm.create_team(team_name)
            existing_users, failed_users = mm.create_users(members)

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
            logging.error('Failed to sync for course {}: {}'.format(course, e.response.text))
            continue
        logger.info('Finished to sync course {}.'.format(course))


if __name__ == "__main__":
    sync()
