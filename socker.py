import os,sys,subprocess,uuid

def main(argv):
    '''Intitialization:'''
    img = None
    cmd = None
    slurm_job_id = None
    verbose = False
    dockerv = None
    dockeruid = None
    dockergid = None
    
    '''Get the UID and GID of the docker user and group'''
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
    
    '''Get the current user information'''
    user = os.getuid()
    group = os.getgid()
    pwd = os.getcwd()
    cid = str(uuid.uuid4())
    home = os.environ['HOME']
    #print 'current UID: ',os.getuid(),'\t Current GID: ',os.getgid()
    #print 'Home dir:',home
    try:
        slurm_job_id = os.environ['SLURM_JOB_ID']
        print 'Slurm job id', slurm_job_id
    except KeyError as e:
        #print e,slurm_job_id
        pass
    
    '''Set the user to root'''
    os.setuid(0)
    os.setuid(0)
    #print 'current UID: ',os.getuid(),'\t Current GID: ',os.getgid()
    
    '''Checking for docker on the system'''
    p = subprocess.Popen('docker --version',shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    out,err = p.communicate()
    #print 'return out and err',out,err
    if p.returncode !=0:
        print 'Docker is not found! Please verify that Docker is installed...'
        sys.exit(2)
    else:
        dockerv = out
    
    '''Get the list of autherized images'''
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
    if argv[0] == '--version':
        print 'Socker version: 0.0.1'
        print 'Docker version: '+dockerv
        sys.exit()
    elif argv[0] == 'images':
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
            print 'You have to specify an image to run'
            sys.exit(2)
        try:
            img = argv[1]
            if not img in images:
                print '"'+img+'" is not an authorized image for this system. Please send a request to hpc-drift@usit.uio.no'
                sys.exit(2)
            if len(argv) >2:
                cmd = ''
                for a in argv[2:]:
                    if ' ' in a or ';' in a or '&' in a:
                        '''composite argument'''
                        a = '"'+a+'"'
                    cmd += a + ' '
                    sys.stderr.write('WARNING: you have a composite argument '+a+' which you''d probably need to run via sh -c')
                cmd = cmd.rstrip()
        except:
            print 'The run command should be: socker run <image> <command>'
            sys.exit(2)
        
    elif argv[0] in ['-h','--help']:
        printHelp()
        sys.exit()
    else:
        print 'invalid option'
        print 'type -h or --help for help'
        sys.exit(2)
    
    '''Compose the docker command'''
    dockercmd = 'docker run --name='+cid+' -d -u '+str(user)+':'+str(group)
    if slurm_job_id:
        dockercmd += ' -v $SCRATCH:$SCRATCH -e SCRATCH=$SCRATCH'    
    dockercmd += ' -v /work/:/work/ -v '+pwd+':'+pwd+' -v '+home+':'+home+' -w '+pwd+' -e HOME='+home+' '+img
    if cmd:
        dockercmd += ' '+cmd
    
    if verbose:
        print 'container command:\n'+cmd+'\n'
        print 'docker command:\n'+dockercmd+'\n'
        print 'executing.....\n'
    
    '''Start the container (run this command as "dockerroot" not as root)'''
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
    '''Get the container's PID'''    
    cpid = subprocess.Popen("docker inspect -f '{{ .State.Pid }}' "+cid, shell=True, stdout=subprocess.PIPE).stdout.read()
    #print 'container PID: ', cpid
    
    if slurm_job_id:
        '''Classify the container process (and all of it's children) to the Slurm's cgroups assigned to the job'''
        cchildren = subprocess.Popen('pgrep -P'+str(cpid), shell=True, stdout=subprocess.PIPE).stdout.read().split('\n')
        cpids = [cpid] + [int(pid) for pid in cchildren if pid.strip() != '']
        print cpids
        for pid in cpids:
            setSlurmCgroups(user,slurm_job_id,pid)
    
    if verbose:
        print 'waiting for the container to exit...\n'
    subprocess.Popen('docker wait '+cid, shell=True, stdout=subprocess.PIPE).stdout.read()
    
    '''After the container exit's, capture it's output'''
    clog = subprocess.Popen("docker inspect -f '{{.LogPath}}' "+str(cid), shell=True, stdout=subprocess.PIPE).stdout.read().rstrip()
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
    subprocess.Popen('docker rm '+cid, shell=True, stdout=subprocess.PIPE).stdout.read()

def reincarnate(user_uid, user_gid):
    def result():
        #print 'uid, gid = %d, %d; %s' % (os.getuid(), os.getgid(), 'starting reincarnation')
        os.setgid(user_gid)
        os.setuid(user_uid)
        #print 'uid, gid = %d, %d; %s' % (os.getuid(), os.getgid(), 'ending reincarnation')
    return result

def printHelp():
    print 'NAME'
    print '\tsocker - Secure runner for Docker containers'
    print '\nSYNOPSIS'
    print '\tsocker run <docker-image> <command>'
    print '\nOPTIONS'
    print '\t--version'
    print '\t\tshow the version number and exit'
    print '\t-h, --help'
    print '\t\tshow this help message and exit'
    print '\t-v, --verbose'
    print '\t\trun in verbose mode'
    print '\timages'
    print '\t\tList the authorized Docker images (found in socker-images)'
    print '\trun IMAGE COMMAND'
    print '\t\tstart a container from IMAGE executing COMMAND as the user'
    print '\nEXAMPLES'
    print '\tList available images'
    print '\t\t$ socker images'
    print '\tRun a CentOS container and print the system release'
    print '\t\t$ socker run centos cat /etc/system-release'
    print '\tRun the previous command in verbose mode'
    print '\t\t$ socker -v run centos cat /etc/system-release'
    print '\nSUPPORT'
    print '\tContact hpc-drift@usit.uio.no'
    print '\n\n'

def setSlurmCgroups(userID,jobID,containerPID):
    cpid = containerPID
    cgroupID = 'slurm/uid_'+str(userID)+'/job_'+str(jobID)+'/step_batch '+str(cpid)
    '''Set the container process free from the docker cgroups'''
    subprocess.Popen('cgclassify -g blkio:/ '+str(cpid), shell=True, stdout=subprocess.PIPE).stdout.read()
    subprocess.Popen('cgclassify -g net_cls:/ '+str(cpid), shell=True, stdout=subprocess.PIPE).stdout.read()
    subprocess.Popen('cgclassify -g devices:/ '+str(cpid), shell=True, stdout=subprocess.PIPE).stdout.read()
    subprocess.Popen('cgclassify -g cpuacct:/ '+str(cpid), shell=True, stdout=subprocess.PIPE).stdout.read()
    subprocess.Popen('cgclassify -g cpu:/ '+str(cpid), shell=True, stdout=subprocess.PIPE).stdout.read()
    '''Include the container process in the Slurm cgroups'''
    subprocess.Popen('cgclassify -g memory:/'+cgroupID, shell=True, stdout=subprocess.PIPE).stdout.read()
    subprocess.Popen('cgclassify -g cpuset:/'+cgroupID, shell=True, stdout=subprocess.PIPE).stdout.read()
    subprocess.Popen('cgclassify -g freezer:/'+cgroupID, shell=True, stdout=subprocess.PIPE).stdout.read()
    
if __name__ == "__main__":
   main(sys.argv[1:])
