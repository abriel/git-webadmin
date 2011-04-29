from django.db import models
from self_libs import git
from self_libs import useful_func
import os
import logging

logger = logging.getLogger('core.custom')


class user(models.Model):
	full_name  = models.CharField(max_length=200, null=True, blank=True)
	short_name = models.CharField(max_length=30, help_text='short name like nickname, just [a-Z0-9].')
	email      = models.EmailField()

	def __unicode__(self):
		if self.full_name is None:
			return self.short_name
			
		return self.full_name

	def count_of_keys(self):
		return self.ssh_keys_set.count()


class ssh_keys(models.Model):

	class Meta:
		verbose_name        = 'ssh key'

	key        = models.TextField()
	user_id    = models.ForeignKey(user)


class repository_system(models.Model):

	GIT_ENGINE_CHOICES = (('gitosis', 'gitosis'), ('gitolite', 'gitolite'))

	class Meta:
		verbose_name        = 'Repository system'

	system_path = models.CharField(
								max_length=250, 
								verbose_name='URL to admin repo', 
								help_text='Example: file:///var/git/repositories/gitosis-admin.git or git@example.com:gitosis-admin.git'
								)
	access_key  = models.TextField(help_text='your private ssh key, which will be used for access to admin repository')
	engine      = models.CharField(
								max_length=50,
								choices=GIT_ENGINE_CHOICES
								)
	
	def __unicode__(self):
		return self.system_path
	
	def fetch_admin_repo(self):
		addition_info = ''
		
		try:
			ssh_key_path = os.path.join('var', 'ssh_key_' + self.id.__str__())
			ssh_key_file = file(ssh_key_path, 'w')
			ssh_key_file.write(self.access_key)
			ssh_key_file.close()
			os.chmod(ssh_key_path, 0600)
		except Exception, e:
			return e, addition_info
			
		try:
			checkout_path = os.path.join('var', 'repo_' + self.id.__str__())
			os.environ['GIT_SSH'] = os.path.join(os.path.realpath(os.path.curdir), 'bin', 'ssh_wrapper')
			if os.path.isdir(checkout_path):
				useful_func.rmall(checkout_path)
			git.clone(self.system_path, checkout_path)
		except Exception, e:
			return e, addition_info
		
		try:
			gconf_path = os.path.join(checkout_path, 'gitosis.conf')
			gconf = file(gconf_path)
			data = {}
			last_line = False
			git_repository.objects.filter(system=self).delete()

			while True:
				if last_line == True:
					break
				if gconf.tell() == os.stat(gconf_path).st_size:
					last_line = True

				line = gconf.readline()

				if ((len(line.strip()) > 0) and (line.strip()[0] == '[')) or (last_line == True):

					if data.has_key('members'):
						for member in data['members'].split(' '):
							member = member.strip()
							if user.objects.filter(short_name=member).count() > 0:
								continue

							logger.info('found user %s' % member)
							u = user()
							u.short_name = u.full_name = member
							u.save()

							member_key_path = os.path.join(checkout_path, 'keydir', member + '.pub' )
							if os.path.isfile( member_key_path ):
								logger.info('importing key file %s for user %s' % (member_key_path, member))
								tmpf = file( member_key_path )
								for tmpkey in tmpf.readlines():
									key = ssh_keys()
									key.key = tmpkey
									key.user_id = u
									key.save()
								tmpf.close()
							else:
								logger.warning('Cannot import key file %s for user %s' % (member_key_path, member))
								
					for access_mode in ['writable', 'readonly']:
						access_mode_dict = { 'writable' : False, 'readonly' : True }
						if data.has_key(access_mode):
							for repo in data[access_mode].split(' '):
								repo = repo.strip()
								if git_repository.objects.filter(name=repo).count() == 0:
									logger.info('found new repository %s' % repo)
									r = git_repository()
									r.name = repo
									r.system = self
									r.save()
								else:
									r = git_repository.objects.filter(name=repo)[0]
							
								if data.has_key('members'):
									for member in data['members'].split(' '):
										related_user = user.objects.filter(short_name=member)[0]
										if access.objects.filter(repository=r, user=related_user, read_only=access_mode_dict[access_mode]).count() > 0:
											continue
										logger.info('added access rule: user %s to repo %s with access mode %s' % (member, repo, access_mode))
										access_obj = access()
										access_obj.repository = r
										access_obj.user = related_user
										access_obj.read_only = access_mode_dict[access_mode]
										access_obj.save()
										
					data = {}
				if len(line.split('=')) > 1:
					data.update( {line.split('=')[0].strip() : line.split('=')[1].strip() })

		except Exception, e:
			return e, addition_info
		
		return None, addition_info


class git_repository(models.Model):

	class Meta:
		verbose_name        = 'Git repository'
		verbose_name_plural = 'Git repositories'

	name       = models.CharField(max_length=200)
	system     = models.ForeignKey(repository_system, verbose_name='repository system')
	
	def __unicode__(self):
		return self.name + ' on ' + self.system.__unicode__()


class access(models.Model):
	repository = models.ForeignKey(git_repository)
	user       = models.ForeignKey(user)
	read_only  = models.BooleanField()
	branch     = models.CharField(max_length=200, null=True, blank=True)

