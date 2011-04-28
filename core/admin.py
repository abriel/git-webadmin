from core.models import user, ssh_keys, git_repository, access, repository_system
from django.contrib import admin

class ssh_keys_inline(admin.StackedInline):
	model = ssh_keys
	extra = 0

class useradmin(admin.ModelAdmin):
	inlines = [ssh_keys_inline]
	list_display = ('full_name', 'email', 'count_of_keys')

class access_users(admin.StackedInline):
	model = access
	extra = 0

class git_repo_admin(admin.ModelAdmin):
	inlines = [access_users]
	list_display = ('name', 'system')

admin.site.register(user, useradmin)

admin.site.register(git_repository, git_repo_admin)
admin.site.register(repository_system)

