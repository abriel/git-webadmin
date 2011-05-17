from django.db import models
from self_libs import git
from self_libs import useful_func
from ConfigParser import RawConfigParser
import os
import logging
from django.db.models.signals import post_delete
from settings import GIT_DEBUG

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
		return self.ssh_keys_set.count()

	def write_key_file(self, repo_system, only_check=False):
		key_file = os.path.join('var', 'repo_' + repo_system.id.__str__(), 'keydir', self.short_name + '.pub')
		if only_check and os.path.isfile(key_file):
			return
		fp = open(key_file, 'w')
		map(lambda x: fp.write(x.key if x.key.endswith('\n') else x.key+'\n'), self.ssh_keys_set.all())
		fp.close()

	def apply_keys(self):
		affected_repository_systems = Repository_System.objects.filter(git_repository__gitosis_access__user=self).distinct()
		for repository_system in affected_repository_systems:
			self.write_key_file(repository_system)
		
		return affected_repository_systems


class ssh_keys(models.Model):

	class Meta:
		verbose_name        = 'ssh key'

	key        = models.TextField()
	user       = models.ForeignKey(user)


class Repository_System(models.Model):

	GIT_ENGINE_CHOICES = (('gitosis', 'gitosis'), ('gitolite', 'gitolite (dev)'))

	class Meta:
		verbose_name        = 'Repository system'

	system_path = models.CharField(
								max_length=250,
								verbose_name='URL to admin repo',
								help_text='Example: file:///var/git/repositories/gitosis-admin.git or git@example.com/gitosis-admin.git'
								)
	access_key  = models.TextField(help_text='your private ssh key, which will be used for access to admin repository')
	engine      = models.CharField(
								max_length=50,
								choices=GIT_ENGINE_CHOICES
								)

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
		addition_info = ''

		try:
			self.set_ssh_env()
		except Exception, e:
			return e, addition_info

		try:
			checkout_path = os.path.join('var', 'repo_' + self.id.__str__())
			if os.path.isdir(checkout_path):
				useful_func.rmall(checkout_path)
			git.clone(self.system_path, checkout_path)
		except Exception, e:
			return e, addition_info

		try:
			gconf_path = os.path.join(checkout_path, 'gitosis.conf')
			gconf = RawConfigParser()
			gconf.read([gconf_path])
			git_repository.objects.filter(system=self).delete()
			system_users = map(lambda x: x.short_name, user.objects.all())

			for section in filter(lambda x: x.startswith('group'), gconf.sections()):
				if 'members' in gconf.options(section):
					for member in gconf.get(section, 'members').split(' '):
						member = member.strip()
						if member in system_users:
							continue

						logger.info('found user %s' % member)
						u = user()
						u.short_name = u.full_name = member
						u.save()
						system_users.append(member)

						member_key_path = os.path.join(checkout_path, 'keydir', member + '.pub' )
						if os.path.isfile( member_key_path ):
							logger.info('importing key file %s for user %s' % (member_key_path, member))
							tmpf = file( member_key_path )
							for tmpkey in tmpf.readlines():
								key = ssh_keys()
								key.key = tmpkey
								key.user = u
								key.save()
							tmpf.close()
						else:
							logger.warning('Cannot import key file %s for user %s' % (member_key_path, member))

				for access_mode in ['writable', 'readonly']:
					access_mode_dict = { 'writable' : False, 'readonly' : True }
					if access_mode in gconf.options(section):
						for repo in gconf.get(section, access_mode).split(' '):
							repo = repo.strip()
							if git_repository.objects.filter(name=repo,system=self).count() == 0:
								logger.info('found new repository %s' % repo)
								r = git_repository()
								r.name = repo
								r.system = self
								r.save()
							else:
								r = git_repository.objects.filter(name=repo,system=self)[0]

							for member in gconf.get(section, 'members').split(' '):
								member = member.strip()
								related_user = user.objects.filter(short_name=member)[0]
								if gitosis_access.objects.filter(repository=r, user=related_user, read_only=access_mode_dict[access_mode]).count() > 0:
									continue
								logger.info('added access rule: user %s to repo %s with access mode %s' % (member, repo, access_mode))
								access_obj = gitosis_access()
								access_obj.repository = r
								access_obj.user = related_user
								access_obj.read_only = access_mode_dict[access_mode]
								access_obj.save()

		except Exception, e:
			return e, addition_info

		return None, addition_info

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
			if user.objects.filter(short_name=user_with_key,gitosis_access__repository__system=self).count() == 0:
				gfile = os.path.join('keydir', user_with_key + '.pub')
				commit_message = 'deleted not needed anymore user\'s keyfile: %s. %s' % (gfile, addition_info)
				grepo.rm(gfile)
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
	user       = models.ForeignKey(user)
	read_only  = models.BooleanField()

	def __unicode__(self):
		wmode = 'writable' if not self.read_only else 'read only'
		return self.user.short_name + ' on ' + self.repository.name + ' mode ' + wmode

	def check_keys(self):
		self.user.write_key_file(self.repository.system, only_check=True)


class gitosis_access(access):
	pass


class gitolite_access(access):
	create_branch = models.BooleanField()
	branch        = models.CharField(max_length=200, null=True, blank=True)


post_delete.connect(ssh_key_post_delete, sender=ssh_keys)
post_delete.connect(access_post_delete,  sender=gitosis_access  )
post_delete.connect(git_repository_post_delete, sender=git_repository )
