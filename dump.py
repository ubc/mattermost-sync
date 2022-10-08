import click
import click_log
import csv
import logging

from mattermostsync import Sync, LDAP_ATTRIBUTES

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
@click.option('-r', '--url', help='Mattermost URL', envvar='MM_URL', required=True)
@click.option('-o', '--port', help='Mattermost port', envvar='MM_PORT', default=443, show_default=True)
@click.option('-t', '--token', help='Mattermost token', envvar='MM_TOKEN', required=True)
@click.option(
    '-s', '--scheme', help='Mattermost scheme', envvar='MM_SCHEME',
    default='https', type=click.Choice(['http', 'https']), show_default=True
)
@click.argument('courses', envvar='COURSE_NAMES')
def dump(ldap, bind, password, base, courses, url, port, token, scheme):
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

    members = mm.get_member_from_ldap(base, courses, attributes=LDAP_ATTRIBUTES + ('ubcEduStudentNumber',))
    with open(courses + '.csv', 'w', newline='') as csvfile:
        writer = csv.writer(
            csvfile, delimiter=',',
            quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for m in members:
            writer.writerow([
                m['username'],
                m['first_name'] if 'first_name' in m else '',
                m['last_name'] if 'last_name' in m else '',
                m['props']['puid'] if 'puid' in m['props'] else '',
                # m['props']['student_number'] if 'student_number' in m['props'] else ''
            ])
    return


if __name__ == "__main__":
    dump()
