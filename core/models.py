from django.db import models


class user(models.Model):
	full_name  = models.CharField(max_length=200)
	email      = models.EmailField()

	def __unicode__(self):
		return self.full_name

	def count_of_keys(self):
		return self.ssh_keys_set.count()


class ssh_keys(models.Model):
	key        = models.TextField()
	user_id    = models.ForeignKey(user)


class git_repository(models.Model):
	name  = models.CharField(max_length=200)


class access(models.Model):
	repository = models.ForeignKey(git_repository)
	user       = models.ForeignKey(user)
	read_only  = models.BooleanField()
	branch     = models.CharField(max_length=200, null=True)

