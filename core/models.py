from django.db import models
from self_libs.gitpy import git
from self_libs import useful_func
from ConfigParser import RawConfigParser
import os
import logging
from django.db.models.signals import post_delete
from settings import GIT_DEBUG
import tempfile
import ConfigParser

logger = logging.getLogger('core.custom')


def ssh_key_post_delete(sender, instance, **kwargs):
	try:
		for rsystem in instance.user.apply_keys():
			rsystem.git_push('[ Initialized by apply keys for user %s / %s ]' % (instance.user.full_name, instance.user.short_name), (not GIT_DEBUG) )
	except user.DoesNotExist:
		pass

def access_post_delete(sender, instance, **kwargs):
	try:
		instance.repository.system.generate_config()
		instance.repository.system.git_push('[ Initialized by changed access rules for repository %s ]' % instance.repository.name, (not GIT_DEBUG) )
	except git_repository.DoesNotExist:
		pass
	
def git_repository_post_delete(sender, instance, **kwargs):
	try:
		instance.system.generate_config()
		instance.system.git_push('[ Initialized by delete repository %s ]' % instance.name, (not GIT_DEBUG) )
	except Repository_System.DoesNotExist:
		pass


class user(models.Model):
	full_name  = models.CharField(max_length=200, null=True, blank=True)
	short_name = models.CharField(max_length=30, help_text='short name like nickname, just [a-Z0-9].')
	email      = models.EmailField(null=True, blank=True)

	def __unicode__(self):
		if self.full_name is None:
			return self.short_name

		return self.full_name

	def count_of_keys(self):
		return self.ssh_key_set.count()

	def write_key_file(self, repo_system, only_check=False):
		key_file = os.path.join('var', 'repo_' + repo_system.id.__str__(), 'keydir', self.short_name + '.pub')
		if only_check and os.path.isfile(key_file):
			return
		fp = open(key_file, 'w')
		map(lambda x: fp.write(x.key if x.key.endswith('\n') else x.key+'\n'), self.ssh_key_set.all())
		fp.close()

	def apply_keys(self):
		affected_repository_systems = Repository_System.objects.filter(git_repository__access__user=self).distinct()
		for repository_system in affected_repository_systems:
			self.write_key_file(repository_system)
		
		return affected_repository_systems


class ssh_key(models.Model):

	class Meta:
		verbose_name        = 'ssh key'

	key        = models.TextField()
	user       = models.ForeignKey(user)
	name       = models.CharField(blank=True, null=True, max_length=20)

	def __unicode__(self):
		return self.name


class Repository_System(models.Model):

	class Meta:
		verbose_name        = 'Repository system'

	system_path = models.CharField(
								max_length=250,
								verbose_name='URL to admin repo',
								help_text='Example: file:///var/git/repositories/gitosis-admin.git or git@example.com/gitosis-admin.git',
								unique=True
								)
	access_key  = models.TextField(help_text='your private ssh key, which will be used for access to admin repository')
	status     = models.SmallIntegerField(default=0, blank=True, null=True)

	def __unicode__(self):
		return self.system_path

	def set_ssh_env(self):
		if os.path.isdir('var') == False:
			os.mkdir('var', 0700)
		ssh_key_path = os.path.join('var', 'ssh_key')
		ssh_key_file = file(ssh_key_path, 'w')
		ssh_key_file.write(self.access_key)
		ssh_key_file.close()
		os.chmod(ssh_key_path, 0600)
		os.environ['GIT_SSH'] = os.path.join(os.path.realpath(os.path.curdir), 'bin', 'ssh_wrapper')

	def fetch_admin_repo(self):
		try:
			self.set_ssh_env()
		except Exception, e:
			return 1, e

		try:
			checkout_path = os.path.join('var', 'repo_' + self.id.__str__())
			if os.path.isdir(checkout_path):
				useful_func.rmall(checkout_path)
			git.clone(self.system_path, checkout_path)
		except Exception, e:
			return 2, e

		try:
			access_map = self._parse_config(checkout_path)
			git_repository.objects.filter(system=self).delete()
			system_users = map(lambda x: x.short_name, user.objects.all())

			for (member, member_keys) in access_map['keys'].items():

				try:
					u = user.objects.filter(short_name=member)[0]
				except IndexError:
					logger.info('found user %s' % member)
					u = user()
					u.short_name = u.full_name = member
					u.save()

				for (member_key_name, member_key_entity) in member_keys.items():
					really_key_name = member_key_name.lstrip(member+'_')
					k = ssh_key()
					k.key, k.user, k.name = member_key_entity, u, really_key_name
					k.save()

			for (repo_name, repo_options) in access_map['repositories'].items():
				logger.info('found new repository %s' % repo_name)
				r = git_repository()
				r.name = repo_name
				r.system = self
				r.save()
				for (access_mode, users) in repo_options.items():
					for (_, member_keys) in users.items():
						for member_key in member_keys:

							try:
								u = user.objects.filter(short_name=member_key.split('_')[0] )[0]
								k = ssh_key.objects.filter(user=u, name=member_key.lstrip(member+'_'))[0]
							except IndexError:
								continue

							readonly = False if access_mode.startswith('rw') else True
							logger.info('added access rule: user %s to repo %s with access mode %s' % (u, repo_name, access_mode))
							access_obj = gitosis_access() if isinstance(self, Gitosis_Repository_System) else gitolite_access()
							access_obj.repository = r
							access_obj.key = k
							access_obj.read_only = readonly
							if access_mode == 'rw+':
								access_obj.create_branch = True
							access_obj.save()

		except Exception, e:
			return 3, e

		return 0, ''

	def git_push(self, addition_info, push=True):
		grepo = git.LocalRepository(os.path.join('var','repo_' + self.id.__str__()))
		for (file_typo, files) in { 'changed': grepo.getChangedFiles(), 'added': grepo.getUntrackedFiles() }.items():
			for gfile in map(lambda x: str(x), files):
				if gfile.endswith('.conf'):
					commit_message = file_typo + ' config file: %s. %s' % (gfile, addition_info)
				elif gfile.startswith('keydir') and gfile.endswith('.pub'):
					commit_message = file_typo + ' keys for user: %s. %s' % (os.path.basename(gfile).partition('.')[0], addition_info)
				grepo.add(gfile)
				grepo.commit(commit_message)
		for user_with_key in map(lambda x: x.partition('.pub')[0],
								filter(lambda x: x.endswith('.pub'),
									os.listdir(os.path.join('var','repo_' + self.id.__str__(), 'keydir')))):
			if user.objects.filter(short_name=user_with_key,access__repository__system=self).count() == 0:
				gfile = os.path.join('keydir', user_with_key + '.pub')
				commit_message = 'deleted not needed anymore user\'s keyfile: %s. %s' % (gfile, addition_info)
				grepo.delete(gfile)
				grepo.commit(commit_message)

		if push == True:
			self.set_ssh_env()
			grepo.push()

	def generate_config(self):
		gconf = RawConfigParser()
		gconf.add_section('gitosis')
		repositories = self.git_repository_set.all()

		for repository in repositories:
			for (access_mode_name, access_mode) in { 'writable' : False, 'readonly' : True }.items():
				members = gitosis_access.objects.filter(repository=repository,read_only=access_mode).all()
				if members.count() > 0:
					current_section = 'group ' + repository.name + '-' + access_mode_name
					gconf.add_section(current_section)
					gconf.set(current_section, 'members', ''.join(map(lambda x: x.user.short_name + ' ', members)))
					gconf.set(current_section, access_mode_name, repository.name)

		gconf_path = os.path.join('var', 'repo_' + self.id.__str__(), 'gitosis.conf')
		fp = open(gconf_path, 'w')
		gconf.write(fp)
		fp.close()


class Member(object):

	def __init__(self, member):
		if member.count('@'):
			self.member_name  = '@'.join(member.split('@')[:-1])
			self.key_name     = self.member_name + '_' + member.split('@')[-1]
			self.raw_key_name = member.split('@')[-1]
		else:
			self.member_name  = member
			self.key_name     = None


class Gitolite_Repository_System(Repository_System):
	
	CONFIG_NAME = 'gitolite.conf'
	
	def _parse_config(self, checkout_path = '.'):
		config_path = os.path.join(checkout_path, self.CONFIG_NAME)
		fp = file(config_path, 'r')
		tmp = tempfile.TemporaryFile()
		for line in fp.readlines():
			if line.startswith('repo'):
				line = '[' + line.strip() + ']'
			if line.startswith('@'):
				tmp.write('[usergroup %s]\n' % line.split('=')[0] )
			tmp.write(line.strip() + '\n')

		tmp.seek(0)
		config = ConfigParser.RawConfigParser()
		config.readfp(tmp)
		tmp.close()

		rs = { 'repositories': {}, 'usergroups': {}, 'keys': {} }

		for file_base in map(lambda x: x.partition('.pub')[0],
								filter(lambda x: x.count('@') and x.endswith('.pub'),
									os.listdir(os.path.join(checkout_path, 'keydir')))):
			user = Member(file_base).member_name
			key_name = Member(file_base).key_name
			fd = open(os.path.join(checkout_path, 'keydir', file_base + '.pub'))
			if not rs['keys'].has_key(user):
				rs['keys'].update( { user: {} } )
			for key in fd.readlines():
				rs['keys'][user].update({ key_name : key })
			fd.close()

		for section in config.sections():
			repo_name = section.split()[1]
			for option in config.options(section):
				if section.startswith('repo'):
					if not rs['repositories'].has_key(repo_name):
						rs['repositories'].update({ repo_name: {} })
					rs['repositories'][repo_name].update( { option: {} } )
					for member_record in config.get(section, option).split():
						if member_record.startswith('@'):
							user = member_record
							if  member_record == '@all':
								keys_name = map(lambda x: x.keys().pop(), rs['keys'].values())
							else:
								keys_name = []
								for member in rs['usergroups'][user[1:]]:
									if not member.count('@'):
										keys_name += rs['keys'][member].keys()
									else:
										keys_name += [Member(member).key_name]
								keys_name = list(set ( keys_name ))

						elif not member_record.count('@'):
							user = member_record
							keys_name = rs['keys'][user].keys()

						else:
							user = Member(member_record).member_name
							keys_name = [ Member(member_record).key_name ]
							
						if not rs['repositories'][repo_name][option].has_key(user):
							rs['repositories'][repo_name][option].update({ user: [] })
						rs['repositories'][repo_name][option][user] += keys_name
						rs['repositories'][repo_name][option][user] = list( set( \
											rs['repositories'][repo_name][option][user] ) )

				elif section.startswith('usergroup'):
					rs['usergroups'].update( { section.split()[1][1:] : config.get(section, option).split() } )

		return rs


class Gitosis_Repository_System(Repository_System):

	CONFIG_NAME = 'gitosis.conf'

	def _parse_config(self, checkout_path = '.'):
		gconf_path = os.path.join(checkout_path, self.CONFIG_NAME)
		gconf = RawConfigParser()
		gconf.read([gconf_path])

		rs = { 'repositories': {}, 'usergroups': {}, 'keys': {} }

		for user in map(lambda x: x.partition('.pub')[0],
								filter(lambda x: x.endswith('.pub'),
									os.listdir(os.path.join(checkout_path, 'keydir')))):
			fd = open(os.path.join(checkout_path, 'keydir', user + '.pub'))
			rs['keys'].update( { user: {} } )
			for key in fd.readlines():
				rs['keys'][user].update({ user + '_key_' + str(len(rs['keys'][user])) : key })
			fd.close()

		for section in gconf.sections():
			for (option, translated_option) in [ ('writable', 'rw'), ('readonly', 'r') ]:
				if gconf.has_option(section, option):
					for repo_name in gconf.get(section, option).strip().split():
						if not rs['repositories'].has_key(repo_name):
							rs['repositories'].update({ repo_name: {} })
						if gconf.has_option(section, 'members'):
							rs['repositories'][repo_name].update( { translated_option: {} } )
							for member in gconf.get(section, 'members').split():
								rs['repositories'][repo_name][translated_option].update( { member: rs['keys'][member].keys() } )

		return rs


class git_repository(models.Model):

	class Meta:
		verbose_name        = 'Git repository'
		verbose_name_plural = 'Git repositories'

	name       = models.CharField(max_length=200)
	system     = models.ForeignKey(Repository_System, verbose_name='repository system')

	def __unicode__(self):
		return self.name + ' on ' + self.system.__unicode__()


class access(models.Model):
	repository = models.ForeignKey(git_repository)
	key       = models.ForeignKey(ssh_key)
	read_only  = models.BooleanField()

	def __unicode__(self):
		wmode = 'writable' if not self.read_only else 'read only'
		return self.key.user.short_name +' key ' + self.key.name + ' on ' + self.repository.name + ' mode ' + wmode

	def check_keys(self):
		self.key.user.write_key_file(self.repository.system, only_check=True)


class gitosis_access(access):
	pass


class gitolite_access(access):
	create_branch = models.BooleanField()
	branch        = models.CharField(max_length=200, null=True, blank=True)


post_delete.connect(ssh_key_post_delete, sender=ssh_key)
post_delete.connect(access_post_delete,  sender=gitosis_access  )
post_delete.connect(git_repository_post_delete, sender=git_repository )
