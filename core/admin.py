from core.models import *
from django.contrib import admin
from django.contrib import messages
from self_libs.gitpy import git
import os
from settings import GIT_DEBUG


class ssh_keys_inline(admin.StackedInline):
	model = ssh_key
	extra = 0

class useradmin(admin.ModelAdmin):
	inlines = [ssh_keys_inline]
	list_display = ('full_name', 'email', 'count_of_keys')

	def save_model(self, request, obj, form, change):
		if change == True:
			previos_short_name = user.objects.get(id=obj.id).short_name
			obj.save()
			try:
				if previos_short_name != obj.short_name:
					affected_repository_systems = Repository_System.objects.filter(git_repository__access__user=obj).distinct()
					for repository_system in affected_repository_systems:
						grepo = git.LocalRepository(os.path.join('var', 'repo_' + repository_system.id.__str__()))
						grepo.mv(os.path.join('keydir', previos_short_name + '.pub'), os.path.join('keydir', obj.short_name + '.pub'))
						grepo.commit('Changed user nickname: %s => %s [ Initialized by save command on user %s / %s ]' % (previos_short_name, obj.short_name, obj.full_name, obj.short_name))
						repository_system.generate_config()
						repository_system.git_push('[ Initialized by save command on user %s / %s ]' % (obj.full_name, obj.short_name), (not GIT_DEBUG) )

				for rsystem in obj.apply_keys():
					rsystem.git_push('[ Initialized by apply keys for user %s / %s ]' % (obj.full_name, obj.short_name), (not GIT_DEBUG) )

			except Exception, e:
				messages.error(request, e)

		else:
			obj.save()

	def save_formset(self, request, form, formset, change):
		instances = formset.save()
		try:
			if len(instances) > 0:
				ssh_key_post_delete(ssh_keys, instances[0])

		except Exception, e:
			messages.error(request, e)


class access_users(admin.StackedInline):
	model = access
	extra = 0

class GitRepositoryAdmin(admin.ModelAdmin):
	inlines = [access_users]
	list_display = ('name', 'system')

	def save_model(self, request, obj, form, change):
		obj.save()

		try:
			obj.system.generate_config()
			messages.success(request, 'config was generated')
			map(lambda x: x.check_keys(), obj.access_set.all())
			messages.info(request, 'user keys was checked')
			messages.info(request, 'trying push changed config to remote server...')
			obj.system.git_push('[ Initialized by save command on repository %s ]' % obj.name, (not GIT_DEBUG) )
			messages.success(request, 'system repository was synced with remote server')
		except Exception, e:
			messages.error(request, e)

	def save_formset(self, request, form, formset, change):
		instances = formset.save()
		try:
			for instance in instances:
				instance.check_keys()
			if len(instances) > 0:
				access_post_delete(access, instances[0])
		except Exception, e:
			messages.error(request, e)


class RepositorySystemAdmin(admin.ModelAdmin):

	def save_model(self, request, obj, form, change):
		obj.save()

		error = ''
		addition_info = ''
		try:
			error, addition_info = obj.fetch_admin_repo()
			if error is not None:
				raise(Exception('raise custom exception'))
		except:
			messages.error(request, 'Cannot apply changes:')
			messages.error(request, 'some problems occurred in checkout system repository or import current config.')
			messages.error(request, 'You should RESAVE changes when problems have been resolved.')
			messages.error(request, 'Error info:')
			messages.error(request, error)
			messages.error(request, 'Additional info:')
			messages.error(request, addition_info)

		if len(addition_info) > 0:
			messages.info(request, 'Additional info:')
			messages.info(request, addition_info)


admin.site.register(user, useradmin)

admin.site.register(git_repository, GitRepositoryAdmin)
admin.site.register(Repository_System, RepositorySystemAdmin)

