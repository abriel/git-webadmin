## git-webadmin

<https://github.com/abriel/git-webadmin>

### What this project provides

You can use this Django based web interface to leverage the use of gitosis to 
manage git repositories and the access to them for users (including their SSH keys).

The project uses the admin interface of Django for the management of gitosis.

### Requirements

* [git](http://git-scm.com/)
* [Django](https://www.djangoproject.com/) (Python Web Framework)
* [gitpy](https://github.com/abriel/gitpy) - included as a git submodule

### Instructions

To get git-webadmin up and running, follow these steps:

    git clone git://github.com/abriel/git-webadmin.git
    cd git-webadmin
    git submodule init
    git submodule update
    # adjust settings.py (at least configure a db in DATABASES)
    python manage.py syncdb
    python manage.py runserver

Now you can reach the server on <http://localhost:8000>.
Go to <http://localhost:8000/admin/> for the interface to the settings.

### More Resources

The more detailed documentation can be found in the
[Russian readme file](https://github.com/abriel/git-webadmin/blob/master/readme.rus).

### Author

* Dmitry Pisarev (https://github.com/abriel)

