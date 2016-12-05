# socker: A wrapper for secure running of Docker containers on [Slurm](https://slurm.schedmd.com/)

Introduction
-------------
Socker is secure for enabling unprivileged users to run Docker containers. It mainly does two things: 
* It enforces running containers within as the user not as root 
* When it is called inside a Slurm job, it enforces the inclusion of containers in the [cgroups assigned by Slurm to the parent jobs](https://slurm.schedmd.com/cgroups.html)

More details are in the [socker manuscript](https://github.com/unioslo/socker/blob/master/socker.pdf)

Design
-------
Socker is composed of one binary that is a compiled python script. While system administrators can be members of the ``docker`` group, regular users can use Docker via Socker.

<img src="https://github.com/unioslo/socker/blob/master/files/socker.png" width="400"><br>

Socker operation workflow is below

<img src="https://github.com/unioslo/socker/blob/master/files/socker-workflow.png" width="600"><br>

Usage
-------
* Install [Nuitka](http://nuitka.net/) with it's prerequisites (python and gcc)
* Compile socker: 
```
nuitka --recurse-on socker.py
```
* Change the owner of the binary to root and enable SUID: 
````
mv socker.exe socker
sudo chown 0:0 socker
sudo chmod +s socker
```
* Create a list of authorized images as root (you need to fix the path to the images file in socker before compiting):
```
sudo vim socker-images
```
* Options:
```
socker --help 

NAME
	socker - Secure runner for Docker containers

SYNOPSIS
	socker run <docker-image> <command>

OPTIONS
	--version
		show the version number and exit
	-h, --help
		show this help message and exit
	-v, --verbose
		run in verbose mode
	images
		List the authorized Docker images (found in socker-images)
	run IMAGE COMMAND
		start a container from IMAGE executing COMMAND as the user

EXAMPLES
	List available images
		$ socker images
	Run a CentOS container and print the system release
		$ socker run centos cat /etc/system-release
	Run the previous command in verbose mode
		$ socker -v run centos cat /etc/system-release

SUPPORT
	Contact hpc-drift@usit.uio.no
```
Prerequisites
--------------
* Docker 1.6+
* You MUST have a group ``docker`` and a user ``dockerroot`` who is member of ONLY the ``docker`` group. The ``docker run`` command will be executed as ``dockerroot``
* Slurm is not a prerequisite, but if you run socker inside a Slurm job, it will put the container under Slurm's control

Support and Bug Reports
-------------------------------
Report an issue on the [issues](https://github.com/unioslo/socker/issues) section or send an email to azab@usit.uio.no
