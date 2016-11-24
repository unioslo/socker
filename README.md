# socker: A wrapper for secure running of Docker containers on Slurm

Usage:
-------
* Install [Nuitka](http://nuitka.net/) with it's prerequisites (python and gcc)
* Compile socker: 
```
nuitka socker.py
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
Prerequisites
--------------
* Docker 1.6+
* Slurm is not a prerequisite, but if you run socker inside a Slurm job, it will put the container under Slurm's control

Manuscript:
------------
[socker manuscript](https://github.com/unioslo/socker/blob/master/socker.pdf)

Support and Bug Reports
-------------------------------
Report an issue on the [issues](https://github.com/unioslo/socker/issues) section or send an email to azab@usit.uio.no
