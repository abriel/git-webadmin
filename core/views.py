from core.models import *
from django.shortcuts import render_to_response
from django.http import Http404, HttpResponseRedirect
from django.template import RequestContext
from django.contrib import messages
from django.core.urlresolvers import reverse


def index(request):
	srepo_list = Repository_System.objects.all()
	return render_to_response('core/index.html', {'srepo_list': srepo_list})
	
def add_system_repository(request):
	try:
		request.POST['submit']
	except KeyError:
		return render_to_response('core/add_system_repository.html', context_instance=RequestContext(request) )

	post_vars = { 
				'git_url' : request.POST['git_url'],
				'ssh_key' : request.POST['ssh_key'],
				'engine'  : request.POST['engine'],
				'submit' : request.POST['submit'],
				}

	if post_vars['submit'] == 'Go to index page':
		return HttpResponseRedirect(reverse('core.views.index'))

	for var in ['git_url', 'ssh_key']:
		if request.POST[var].strip() == '':
			return render_to_response('core/add_system_repository.html', post_vars, context_instance=RequestContext(request) )

	if Repository_System.objects.filter(system_path=post_vars['git_url']).count() and \
			Repository_System.objects.filter(system_path=post_vars['git_url'])[0].status == 0:
		err_msg = 'You can not add this repository, because it already exists. You can edit it.'
		post_vars.update( { 'error' : err_msg, 'status': 3 } )
		return render_to_response('core/add_system_repository.html', post_vars,	context_instance=RequestContext(request) )

	try:
		if Repository_System.objects.filter(system_path=post_vars['git_url']).count():
			system_repository = Gitosis_Repository_System.objects.filter(system_path=post_vars['git_url'])[0] if post_vars['engine'] == 'gitosis' \
				else Gitolite_Repository_System.objects.filter(system_path=post_vars['git_url'])[0]
	except IndexError:
		err_msg = 'You can not change repository engine.'
		post_vars.update( { 'error' : err_msg, 'status': 4 } )
		return render_to_response('core/add_system_repository.html', post_vars,	context_instance=RequestContext(request) )

	if Repository_System.objects.filter(system_path=post_vars['git_url']).count() == 0:
		system_repository = Gitosis_Repository_System() if post_vars['engine'] == 'gitosis' \
			else Gitolite_Repository_System()

	system_repository.system_path = post_vars['git_url']
	system_repository.access_key  = post_vars['ssh_key']
	system_repository.status = 2
	system_repository.save()

	err_code, err_msg = system_repository.fetch_admin_repo()
	if err_code:
		post_vars.update( { 'error' : err_msg, 'status': system_repository.status } )
		return render_to_response('core/add_system_repository.html', post_vars,	context_instance=RequestContext(request) )

	system_repository.status = 0
	system_repository.save()
	return HttpResponseRedirect(reverse('core.views.index'))
