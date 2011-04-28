from django.db import models


class user(models.Model):
	full_name  = models.CharField(max_length=200, null=True, blank=True)
	short_name = models.CharField(max_length=30, help_text='short name like nickname, just [a-Z0-9].')
	email      = models.EmailField()

	def __unicode__(self):
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

