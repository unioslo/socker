# Installing Docker on CentOS 6.x cluster with BeeGFS

Last supported docker for CentOS 6.x is docker 1.7 which doesn't support BeeGFS as a backing file-system. And if the local disk of compute nodes is small, the solution will be creating ext4 images on beegfs. The following must run as root:

* Assuming the shared file-system for shared images is ``/work/docker``, Create a 120 GiB ext4 image for each docker compute node, then on each compute node:
```bash
mkdir /docker
mount -o loop /work/docker/<node-name>.ext4 /docker
```
* Now install docker 1.7 (don't follow the instructions from docker.com because CentOS 6 is not there):
```bash
yum install docker-io -y
```
* Tell docker to use /docker to store containers
```bash
vim /etc/sysconfig/docker
# >> set other_args=-g /docker
```
* If docker complained, do the following instead:
```bash
mv /var/lib/docker /docker/
ln -s /docker/docker /var/lib/docker
```
* Create the docker group and add the dockerroot user to it:
```bash
groupadd docker
usermod -aG docker dockerroot
```
* Start docker service and configure it to start on boot
```bash
service docker start
chkconfig docker on
```
