from core.models import user, ssh_keys, git_repository, access, Repository_System
from django.contrib import admin
from django.contrib import messages

class ssh_keys_inline(admin.StackedInline):
	model = ssh_keys
	extra = 0

class useradmin(admin.ModelAdmin):
	inlines = [ssh_keys_inline]
	list_display = ('full_name', 'email', 'count_of_keys')

class access_users(admin.StackedInline):
	model = access
	extra = 0

class GitRepositoryAdmin(admin.ModelAdmin):
	inlines = [access_users]
	list_display = ('name', 'system')

	def save_model(self, request, obj, form, change):
		obj.save()

		try:
			obj.generate_config()
			messages.success(request, 'config was generated')
			messages.info(request, 'trying push changed config to remote server...')
			obj.system.git_push('[ Initialized by save command on repository %s ]' % obj.name )
			messages.success(request, 'system repository was synced with remote server')
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

