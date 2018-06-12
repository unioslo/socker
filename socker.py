import os,sys,subprocess,uuid

VERSION = "16.12"

def setSlurmCgroups(userID,jobID,containerPID,verbose=False):
    cpid = containerPID
    cgroupID = 'slurm/uid_'+str(userID)+'/job_'+str(jobID)+'/step_batch '+str(cpid)
    # Set the container process free from the docker cgroups
    subprocess.Popen('cgclassify -g blkio:/ '+str(cpid), shell=True, stdout=subprocess.PIPE)
    subprocess.Popen('cgclassify -g net_cls:/ '+str(cpid), shell=True, stdout=subprocess.PIPE)
    subprocess.Popen('cgclassify -g devices:/ '+str(cpid), shell=True, stdout=subprocess.PIPE)
    subprocess.Popen('cgclassify -g cpuacct:/ '+str(cpid), shell=True, stdout=subprocess.PIPE)
    subprocess.Popen('cgclassify -g cpu:/ '+str(cpid), shell=True, stdout=subprocess.PIPE)
    # Include the container process in the Slurm cgroups
    out = ''
    out += 'adding '+str(cpid)+' to Slurm\'s memory cgroup: '+\
    subprocess.Popen('cgclassify -g memory:/'+cgroupID, shell=True, stdout=subprocess.PIPE).stdout.read()
    out += '\nadding '+str(cpid)+' to Slurm\'s cpuset cgroup: '+\
    subprocess.Popen('cgclassify -g cpuset:/'+cgroupID, shell=True, stdout=subprocess.PIPE).stdout.read()
    out += '\nadding '+str(cpid)+' to Slurm\'s freezer cgroup: '+\
    subprocess.Popen('cgclassify -g freezer:/'+cgroupID, shell=True, stdout=subprocess.PIPE).stdout.read()
    if verbose:
        print out
    
def reincarnate(user_uid, user_gid):
    def result():
        #print 'uid, gid = %d, %d; %s' % (os.getuid(), os.getgid(), 'starting reincarnation')
        os.setgid(user_gid)
        os.setuid(user_uid)
        #print 'uid, gid = %d, %d; %s' % (os.getuid(), os.getgid(), 'ending reincarnation')
    return result

def printHelp():
    helpstr = """NAME
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

    """
    print helpstr

def main(argv):
    # Intitialization
    img = None
    cmd = None
    slurm_job_id = None
    verbose = False
    dockerv = None
    dockeruid = None
    dockergid = None

    # checking if help is needed first
    if argv[0] in ['-h','--help']:
        printHelp()
        sys.exit()    
    
    # Get the UID and GID of the docker user and group
    import pwd,grp
    try:
        dockeruid = pwd.getpwnam('dockerroot').pw_uid
        dockergid = grp.getgrnam('docker').gr_gid
    except KeyError:
        print 'There must exist a user "dockerroot" and a group "docker"'
        sys.exit(2)
    if not [g.gr_name for g in grp.getgrall() if 'dockerroot' in g.gr_mem] == ['docker']:
        print 'The user "dockerroot" must be a member of ONLY the "docker" group'
        sys.exit(2)
    
    # Get the current user information
    user = os.getuid()
    group = os.getgid()
    PWD = os.getcwd()
    cid = str(uuid.uuid4())
    home = pwd.getpwuid(user).pw_dir
    #print 'current UID: ',os.getuid(),'\t Current GID: ',os.getgid()
    #print 'Home dir:',home
    try:
        slurm_job_id = os.environ['SLURM_JOB_ID']
        print 'Slurm job id', slurm_job_id
    except KeyError as e:
        #print e,slurm_job_id
        pass
    
    # Set the user to root
    os.setuid(0)
    os.setuid(0)
    #print 'current UID: ',os.getuid(),'\t Current GID: ',os.getgid()
    
    # Checking for docker on the system
    p = subprocess.Popen('/usr/bin/docker --version',shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    out,err = p.communicate()
    #print 'return out and err',out,err
    if p.returncode !=0:
        print 'Docker is not found! Please verify that Docker is installed...'
        sys.exit(2)
    else:
        dockerv = out

    if argv[0] == '--version':
        print 'Socker version: release '+VERSION
        print 'Docker version: '+dockerv
        sys.exit()

    
    # Get the list of autherized images
    try:
        images = filter(None,[line.strip() for line in open('/cluster/tmp/socker-images','r')])
        if len(images) == 0:
            raise Exception()
    except:
        print 'No authorized images to run. Socker cannot be used at the moment.\nContact hpc-drift@usit.uio.no\n'
        sys.exit(2)
        
    if argv[0] in ['-v','--verbose']:
        del argv[0]
        verbose = True
        if len(argv) == 0:
            print 'You need to specify options to run in verbose mode'
            sys.exit(2)
    if argv[0] == 'images':
        print '\n'.join(images)
        sys.exit()
        ##This part should be used when you have a secure local docker registry
        # p = subprocess.Popen('docker images', shell=True, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        # out,err = p.communicate()
        # if p.returncode == 0:
        #     print out
        #     sys.exit()
        # else:
        #     print err
        #     sys.exit(2)
    elif argv[0] == 'run':
        if len(argv) < 2:
            print 'You need to specify an image to run'
            sys.exit(2)
        try:
            img = argv[1]
            if not img in images:
                print '"'+img+'" is not an authorized image for this system. Please send a request to hpc-drift@usit.uio.no'
                sys.exit()
            if len(argv) >2:
                cmd = ''
                for a in argv[2:]:
                    if ' ' in a or ';' in a or '&' in a:
                        # composite argument
                        a = '"'+a+'"'
                        sys.stderr.write('WARNING: you have a composite argument '+a+' which you\'d probably need to run via sh -c\n')
                    if 'docker' in a:
                        print('For security reasons, you cannot include "docker" in your command')
                        sys.exit()
                    cmd += a + ' '
                cmd = cmd.rstrip()
            else:
                print 'You need to specify a command to run'
                sys.exit(2)
                
        except:
            print 'The run command should be: socker run <image> <command>'
            sys.exit(2)
        
    else:
        print 'invalid option'
        print 'type -h or --help for help'
        sys.exit(2)
    
    # Compose the docker command
    dockercmd = '/usr/bin/docker run --name='+cid+' -d -u '+str(user)+':'+str(group)
    if slurm_job_id:
        dockercmd += ' -v $SCRATCH:$SCRATCH -e SCRATCH=$SCRATCH'    
    dockercmd += ' -v /work/:/work/ -v '+PWD+':'+PWD+' -v '+home+':'+home+' -w '+PWD+' -e HOME='+home+' '+img
    if cmd:
        dockercmd += ' '+cmd
    
    if verbose:
        print 'container command:\n'+cmd+'\n'
        print 'docker command:\n'+dockercmd+'\n'
        print 'executing.....\n'
    
    # Start the container (run this command as "dockeruser" not as root)
    p = subprocess.Popen(dockercmd, preexec_fn=reincarnate(dockeruid,dockergid), shell=True, \
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    
    out,err = p.communicate()
    if p.returncode != 0:
        print '#Error: '+err
        sys.exit(2)
    elif verbose:
        print err
        print 'container ID:\n',out
    #print 'current UID: ',os.getuid(),'\t Current GID: ',os.getgid()
    
    if slurm_job_id:
        # Get the container's PID
        cpid = int(subprocess.Popen("/usr/bin/docker inspect -f '{{ .State.Pid }}' "+cid,\
                                shell=True, stdout=subprocess.PIPE).stdout.read().strip())
        #print 'container PID: ', cpid
        # Classify the container process (and all of it's children) to the Slurm's cgroups assigned to the job
        cchildren = subprocess.Popen('pgrep -P'+str(cpid), shell=True, stdout=subprocess.PIPE).stdout.read().split('\n')
        cpids = [cpid] + [int(pid) for pid in cchildren if pid.strip() != '']
        #print cpids
        for pid in cpids:
            setSlurmCgroups(user,slurm_job_id,pid,verbose)
    
    if verbose:
        print 'waiting for the container to exit...\n'
    subprocess.Popen('/usr/bin/docker wait '+cid, shell=True, stdout=subprocess.PIPE).stdout.read()
    
    # After the container exit's, capture it's output
    clog = subprocess.Popen("/usr/bin/docker inspect -f '{{.LogPath}}' "+str(cid), shell=True, stdout=subprocess.PIPE).stdout.read().rstrip()
    with open(clog,'r') as f:
        if verbose:
            print 'container output:\n'
        for line in f:
            d = eval(line.replace('\n',''))
            if d['stream'] == 'stderr':
                sys.stdout.write('#Error: '+d['log'])
            else:
                sys.stdout.write(d['log'])
    if verbose:        
        print '\nremoving the container...\n'
    subprocess.Popen('/usr/bin/docker rm '+cid, shell=True, stdout=subprocess.PIPE).stdout.read()

if __name__ == "__main__":
   main(sys.argv[1:])
