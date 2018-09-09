from setuptools import setup

setup(
   name='Mattermost-Sync',
   version='1.0',
   description='Sync LDAP groups to Mattermost team',
   author='Pan Luo',
   author_email='pan.luo@ubc.ca',
   packages=['mattermostsync'],  #same as name
   install_requires=[
      'python-ldap>=3.1.0,<3.2',
      'mattermostdriver',
      'click',
   ]
)