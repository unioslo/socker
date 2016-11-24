import os,sys,subprocess,getopt,uuid

def main(argv):
    '''Intitialization:'''
    img = None
    cmd = None
    slurm_job_id = None
    verbose = False
    dockerv = None
    
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
    os.setuid(0)
    os.setgid(0)
    #print 'setuid and gid done to root...'
    
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
        ## This part should be used if you have a secure local registry installed 
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
                    if ' ' in a:
                        '''composite argument'''
                        a = '"'+a+'"'
                    cmd += a + ' '
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
        dockercmd += ' -v $SCRATCH:$SCRATCH -v -e SCRATCH=$SCRATCH'    
    dockercmd += ' -v /work/:/work/ -v '+pwd+':'+pwd+' -v '+home+':'+home+' -w '+pwd+' -e HOME='+home+' '+img
    if cmd:
        dockercmd += ' '+cmd
    
    if verbose:
        print 'container command:\n'+cmd+'\n'
        print 'docker command:\n'+dockercmd+'\n'
        print 'executing.....\n'
    
    '''Start the container'''
    p = subprocess.Popen(dockercmd, shell=True, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    out,err = p.communicate()
    if p.returncode != 0:
        print err
        sys.exit(2)
    elif verbose:
        print err
        print 'container ID:\n',out
    
    '''Get the container's PID'''    
    cpid = subprocess.Popen("docker inspect -f '{{ .State.Pid }}' "+cid, shell=True, stdout=subprocess.PIPE).stdout.read()
    #print 'container PID: ', cpid
    
    '''Classify the container process to the Slurm's cgroups'''
    if slurm_job_id:
        setSlurmCgroups(user,slurm_job_id,cpid)
    
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
        print '\nremoving the container...'
    subprocess.Popen('docker rm '+cid, shell=True, stdout=subprocess.PIPE).stdout.read()

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
   
