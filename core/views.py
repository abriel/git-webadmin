from core.models import Repository_System
from django.shortcuts import render_to_response

def index(request):
	srepo_list = Repository_System.objects.all()
	return render_to_response('core/index.html', {'srepo_list': srepo_list})
	