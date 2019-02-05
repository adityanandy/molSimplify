## @file qcgen.py
#  Generates quantum chemistry input files
#  
#  Written by Tim Ioannidis and JP Janet for HJK Group
#
#  Dpt of Chemical Engineering, MIT

from molSimplify.Classes.globalvars import *
import glob, sys, os, shutil
from molSimplify.Classes.mol3D import mol3D
from molSimplify.Classes.atom3D import atom3D
from molSimplify.Classes.globalvars import *

## Generate multiple terachem runs if multiple methods requested
#  @param args Namespace of arguments
#  @param strfiles List of xyz files produced
#  @return List of job directories
def multitcgen(args,strfiles):
    jobdirs = []
    method = False
    if args.method and len(args.method) > 1:
        methods = args.method
        for method in methods:
            jobdirs.append(tcgen(args,strfiles,method))
    else:
        jobdirs.append(tcgen(args,strfiles,method))
    # remove original files
    if not args.jobdir:
        for xyzf in strfiles:
            try:
                os.remove(xyzf+'.xyz')
                os.remove(xyzf+'.molinp')
                os.remove(xyzf+'.report')
            except:
                pass
    return jobdirs

## Generate terachem input files
#  @param args Namespace of arguments
#  @param strfiles List of xyz files produced
#  @param method Method (e.g. b3lyp)
#  @return List of job directories
def tcgen(args,strfiles,method):
    # global variables
    globs = globalvars()
    jobdirs = []
    coordfs = []
    # Initialize the jobparams dictionary with mandatory/useful keywords. TG: removed min_coordinates cartesian
    jobparams={'run': 'minimize',
           'timings': 'yes',
           'maxit': '500',
           'scrdir': './scr',
           'method': 'b3lyp',
           'basis': 'lacvps_ecp',
           'spinmult': '1',
           'charge': '0',
           'gpus': '1',
            }
    # if multiple methods requested generate c directories
    # Overwrite plus add any new dictionary keys from commandline input.       
    for xyzf in strfiles:
        rdir = xyzf.rsplit('/',1)[0]
        xyzft = xyzf.rsplit('/',1)[-1]
        xyzf += '.xyz'
        coordfs.append(xyzf.rsplit('/',1)[-1])
        coordname = xyzft
        # Setting jobname for files + truncated name for queue.
        if len(coordname) > 10:
            nametrunc=coordname
        else:
            nametrunc=coordname
        if not os.path.exists(rdir+'/'+nametrunc) and not args.jobdir:
            os.mkdir(rdir+'/'+nametrunc) 
        mdir = rdir+'/'+nametrunc
        if method:
            if method[0]=='U' or method[0]=='u':
                mmd = '/'+method[1:]
            else:
                mmd = '/'+method
            mdir = rdir+'/'+nametrunc+mmd
            if not os.path.exists(mdir):
                os.mkdir(mdir)
        if not args.jobdir:
            jobdirs.append(mdir)
            shutil.copy2(xyzf,mdir)
            shutil.copy2(xyzf.replace('.xyz','.molinp'),mdir.replace('.xyz','.molinp'))
            try:
                shutil.copy2(xyzf.replace('.xyz','.report'),mdir.replace('.xyz','.report'))
            except:
                pass
        elif args.jobdir:
             jobdirs.append(rdir)
    # parse extra arguments
    # Method parsing, does not check if a garbage method is used here:
    unrestricted=False
    if method:
        jobparams['method'] = method
        if ('u' or 'U') in method[0]:
            # Unrestricted calculation
            unrestricted=True
        else:
            # Restricted calculation
            unrestricted=False
            if args.spin and int(args.spin) > 1:
                jobparams['method'] = 'u'+method
                unrestricted=True
    else:
        if args.spin and int(args.spin) >= 1:
                jobparams['method'] = 'ub3lyp'
                unrestricted=True
        else:
            jobparams['method'] = 'b3lyp'
    if (args.runtyp and 'energy' in args.runtyp.lower()):
        jobparams['run'] = 'energy'
    elif (args.runtyp and 'ts' in args.runtyp.lower()):
        jobparams['run'] = 'ts'
    elif (args.runtyp and 'gradient' in args.runtyp.lower()):
        jobparams['run'] = 'gradient'
    if (args.gpus):
        jobparams['gpus'] = args.gpus
    if (args.dispersion):
        jobparams['dispersion']=args.dispersion
    # Just carry over spin and charge keywords if they're set. Could do checks, none for now.
    if args.spin:
        jobparams['spinmult']=args.spin
    if args.charge:
        if args.bcharge:
            args.charge = int(args.charge)+int(args.bcharge)
        jobparams['charge']=args.charge
    # Check for existence of basis and sanitize name
    if args.basis:
        ecp=False # Flag not currently used, for deciding gpus_ecp code or not later. Can always specify with 'extra' command
        if '*' in args.basis:
            jobparams['basis']=args.basis.replace('*','s')
        else:
            jobparams['basis']=args.basis
    # Overwrite plus add any new dictionary keys from commandline input.       
    if args.qoption:
        if len(args.qoption)%2!=0:
                print 'WARNING: wrong number of arguments in -qoption'
        else:
            for elem in range(0,int(0.5*len(args.qoption))):
                key,val=args.qoption[2*elem],args.qoption[2*elem+1]
                jobparams[key]=val
    # Extra keywords for unrestricted. 
    if unrestricted:
       # If running unrestricted, assume convergence will be more difficult for now.
       jobparams['scf']='diis+a' 
       if not jobparams.has_key('levelshift'):
          jobparams['levelshift']='yes'
       elif jobparams['levelshift'] != 'yes':
          print("Warning! You're doing an unrestricted calculation but have set levelshift = %s" %(jobparams['levelshift']))
       if not jobparams.has_key('levelshiftvala'):
          jobparams['levelshiftvala']='0.25'
       if not jobparams.has_key('levelshiftvalb'):
          jobparams['levelshiftvalb']='0.25'
    # Now we're ready to start building the input file
    if not args.jobdir:
        for i,jobd in enumerate(jobdirs):
            output=open(jobd+'/terachem_input','w')
            output.write('# file created with %s\n' % globs.PROGRAM)
            jobparams['coordinates'] = coordfs[i]
            for keys in jobparams.keys():
                output.write('%s %s\n' %(keys,jobparams[keys]))
            if  jobparams['run'] == 'minimize':
                output.write('new_minimizer yes\n')
                #output.write('min_coordinates cartesian\n')
            if args.tc_fix_dihedral:
                temp = mol3D()
                temp.readfromxyz(strfiles[i])
                metal_ind = temp.findMetal()
                fixed_atoms = list()
                fixed_atoms = temp.getBondedAtoms(metal_ind)
                fixed_atoms = [str(int(i)+1) for i in fixed_atoms] # 1-based indices
                string_to_write = 'dihedral 0 ' + '_'.join(fixed_atoms)
                #print(string_to_write)
                output.write('$constraint_set \n')
                output.write(string_to_write + '\n')
            output.write('end\n')
            output.close()
    elif args.jobdir:
        for i,jobd in enumerate(jobdirs):
            print('jobd is ' + jobd)
            if args.name:
                output=open(jobd+ '/'+args.name + '.in','w')
            else:
                output=open(jobd+'/terachem_input','w')
            output.write('# file created with %s\n' % globs.PROGRAM)
            jobparams['coordinates'] = coordfs[i]
            for keys in jobparams.keys():
                output.write('%s %s\n' %(keys,jobparams[keys]))
            if  jobparams['run'] == 'minimize':
                output.write('new_minimizer yes\n')
                #output.write('min_coordinates cartesian\n')
            if args.tc_fix_dihedral:
                temp = mol3D()
                temp.readfromxyz(strfiles[i])
                metal_ind = temp.findMetal()
                fixed_atoms = list()
                fixed_atoms = temp.getBondedAtoms(metal_ind)
                fixed_atoms = [str(int(i)+1) for i in fixed_atoms] # 1-based indices
                string_to_write = 'dihedral 0 ' + '_'.join(fixed_atoms)
                #print(string_to_write)
                output.write('$constraint_set \n')
                output.write(string_to_write + '\n')
            output.write('end\n')
            output.close()
    return jobdirs

## Converts normal xyz file to gxyz (GAMESS format) file
#  @param filename Filename of xyz file
#  @return Filename of gxyz file
def xyz2gxyz(filename):
    mol=mol3D() # create mol3D object
    mol.readfromxyz(filename) # read molecule
    gfilename = filename.replace('.xyz','.gxyz') # new file name
    mol.writegxyz(gfilename) # write gamess formatted xyz file
    return gfilename.split('.gxyz')[0]

## Generate multiple GAMESS runs if multiple methods requested
#  @param args Namespace of arguments
#  @param strfiles List of xyz files produced
#  @return List of job directories
def multigamgen(args,strfiles):
    method = False
    jobdirs=[]
    if args.method and len(args.method) > 1:
        methods = args.method
        for method in methods:
            jobdirs.append(gamgen(args,strfiles,method))
    else:
        jobdirs.append(gamgen(args,strfiles,method))
    # remove original files
    for xyzf in strfiles:
        os.remove(xyzf+'.xyz')
        os.remove(xyzf+'.gxyz')
        os.remove(xyzf+'.molinp')
    return jobdirs

## Generate GAMESS input files
#  @param args Namespace of arguments
#  @param strfiles List of xyz files produced
#  @param method Method (e.g. b3lyp)
#  @return List of job directories
def gamgen(args,strfiles,method):
    # get global variables
    globs = globalvars()
    jobdirs = []
    coordfs = []
    # Initialize the jobparams dictionary with mandatory/useful keywords.
    jobparams={'RUNTYP': 'OPTIMIZE',
           'GBASIS': 'N21',
           'MAXIT': '500',
           'DFTTYP': 'B3LYP',
           'SCFTYP': 'UHF',
           'ICHARG': '0',
           'MULT': '1',
            }
    # Overwrite plus add any new dictionary keys from commandline input.       
    for xyzf in strfiles:
        # convert to "gamess format"
        xyzf = xyz2gxyz(xyzf+'.xyz')
        rdir = xyzf.rsplit('/',1)[0]
        xyzft = xyzf.rsplit('/',1)[-1]
        xyzf += '.gxyz'
        coordfs.append(xyzf)
        coordname = xyzft
        # Setting jobname for files + truncated name for queue.
        if len(coordname) > 10:
            nametrunc=coordname[0:6]+coordname[-4:]
        else:
            nametrunc=coordname
        if not os.path.exists(rdir+'/'+nametrunc):
            os.mkdir(rdir+'/'+nametrunc) 
        mdir = rdir+'/'+nametrunc
        if method:
            if method[0]=='U' or method[0]=='u':
                mmd = '/'+method[1:]
            else:
                mmd = '/'+method
                jobparams['SCFTYP']='RHF'
            mdir = rdir+'/'+nametrunc+mmd
            if not os.path.exists(mdir):
                os.mkdir(mdir)
        jobdirs.append(mdir)
        shutil.copy2(xyzf,mdir)
        shutil.copy2(xyzf.replace('.gxyz','.molinp'),mdir.replace('.gxyz','.molinp'))
        try:
            shutil.copy2(xyzf.replace('.xyz','.report'),mdir.replace('.xyz','.report'))
        except:
            pass

    if method:
        if method[0]=='U' or method[0]=='u':
            method = method[1:]
    # Just carry over spin and charge keywords if they're set. Could do checks, none for now.
    if args.spin:
       jobparams['MULT']=str(args.spin)
    if args.charge:
       jobparams['ICHARG']=str(args.charge)
    # Check for existence of basis and sanitize name
    if args.gbasis:
          jobparams['GBASIS']=args.gbasis.upper()
    if args.ngauss:
          jobparams['NGAUSS']=args.ngauss.upper()
    if method:
          jobparams['DFTTYP']=method.upper()
    if (args.runtyp and 'en' in args.runtyp.lower()):
        jobparams['run'] = 'ENERGY'
    elif (args.runtyp and 'ts' in args.runtyp.lower()):
        jobparams['run'] = 'SADPOINT'
    # Now we're ready to start building the input file and the job script
    for i,jobd in enumerate(jobdirs):
        output=open(jobd+'/gam.inp','w')
        f=open(coordfs[i])
        s = f.read() # read coordinates
        f.close()
        jobparams['coordinates'] = s
        output.write('! File created using %s\n' % globs.PROGRAM)
        # write $BASIS block
        output.write(' $BASIS ')
        if args.ngauss:
            output.write(' GBASIS='+jobparams['GBASIS'])
            output.write(' NGAUSS='+jobparams['NGAUSS'])
        else:
            output.write(' GBASIS='+jobparams['GBASIS'])
        if args.ndfunc:
            output.write(' NDFUNC='+args.ndfunc)
        if args.npfunc:
            output.write(' NPFUNC='+args.npfunc)
        output.write(' $END\n')
        # write $SYSTEM block
        output.write(' $SYSTEM ')
        # check if MWORDS specified by the user
        if not args.sysoption or not ('MWORDS' in args.sysoption):
            output.write(' MWORDS=16')
        # write additional options
        if (args.sysoption):
            if len(args.sysoption)%2 > 0:
                print 'WARNING: wrong number of arguments in -sysoption'
            else:
                for elem in range(0,int(0.5*len(args.sysoption))):
                    key,val=args.sysoption[2*elem],args.sysoption[2*elem+1]
                    output.write(' '+key+'='+val+' ')
        output.write(' $END\n')
        # write CONTRL block
        output.write(' $CONTRL SCFTYP='+jobparams['SCFTYP']+' DFTTYP=')
        output.write(jobparams['DFTTYP']+' RUNTYP='+jobparams['RUNTYP'])
        output.write('\n  ICHARG='+jobparams['ICHARG']+' MULT=')
        # check if CC basis set specified and add spherical
        if 'CC' in jobparams['GBASIS']:
            output.write(jobparams['MULT']+' ISPHER=1\n')
        else:
            output.write(jobparams['MULT']+'\n')
        # write additional options
        if (args.ctrloption):
            if len(args.ctrloption)%2 > 0:
                print 'WARNING: wrong number of arguments in -ctrloption'
            else:
                for elem in range(0,int(0.5*len(args.ctrloption))):
                    key,val=args.ctrloption[2*elem],args.ctrloption[2*elem+1]
                    output.write(' '+key+'='+val+' ')
        output.write(' $END\n')
        # write $SCF block
        output.write(' $SCF ')
        # check if options specified by the user
        if not args.scfoption or not ('DIRSCF' in args.scfoption):
            output.write(' DIRSCF=.TRUE.')
        if not args.scfoption or not ('DIIS' in args.scfoption):
            output.write(' DIIS=.TRUE.')
        if not args.scfoption or not ('SHIFT' in args.scfoption):
                output.write(' SHIFT=.TRUE.')
        # write additional options
        if (args.scfoption):
            if len(args.scfoption)%2!=0:
                print 'WARNING: wrong number of arguments in -scfoption'
            else:
                for elem in range(0,int(0.5*len(args.scfoption))):
                    key,val=args.scfoption[2*elem],args.scfoption[2*elem+1]
                    output.write(' '+key+'='+val+' ')
        output.write(' $END\n')
        # write $STATPT block
        output.write(' $STATPT ')
        # check if NSTEP specified by the user
        if not args.statoption or not ('NSTEP' in args.statoption):
            output.write(' NSTEP=100')
        # write additional options
        if (args.statoption):
            if len(args.statoption)%2 > 0:
                print 'WARNING: wrong number of arguments in -statoption'
            else:
                for elem in range(0,int(0.5*len(args.statoption))):
                    key,val=args.statoption[2*elem],args.statoption[2*elem+1]
                    output.write(' '+key+'='+val+' ')
        output.write(' $END\n')
        # write $DATA block
        output.write(' $DATA\n')
        output.write(jobparams['coordinates']+' $END\n')
        output.close()
    return jobdirs

## Generate multiple QChem runs if multiple methods requested
#  @param args Namespace of arguments
#  @param strfiles List of xyz files produced
#  @return List of job directories
def multiqgen(args,strfiles):
    method = False
    jobdirs=[]
    if args.method and len(args.method) > 1:
        methods = args.exchange
        for method in methods:
            jobdirs.append(qen(args,strfiles,method))
    else:
        jobdirs.append(qgen(args,strfiles,method))
    # remove original files
    for xyzf in strfiles:
        os.remove(xyzf+'.xyz')
        os.remove(xyzf+'.molinp')
        os.remove(xyzf + '.report')
    return jobdirs

## Generate QChem input files
#  @param args Namespace of arguments
#  @param strfiles List of xyz files produced
#  @param method Method (e.g. b3lyp)
#  @return List of job directories
def qgen(args,strfiles,method):
    # get global variables
    globs = globalvars()
    jobdirs = []
    coordfs = []
    # Initialize the jobparams dictionary with mandatory/useful keywords.
    jobparams={'UNRESTRICTED': 'true',
           'BASIS': 'lanl2dz',
           'JOBTYPE': 'opt',
            'EXCHANGE': 'b3lyp',
           'CORRELATION': 'none',
           'MAX_SCF_CYCLES': '500',
           'GEOM_OPT_MAX_CYCLES': '1000',
           'SYMMETRY': 'off',
           'PRINT_ORBITALS': 'true',
           'CHARGE':'1',
           'SPIN':'1',
            }
    # Overwrite plus add any new dictionary keys from commandline input.       
    for xyzf in strfiles:
        rdir = xyzf.rsplit('/',1)[0]
        xyzft = xyzf.rsplit('/',1)[-1]
        xyzf += '.xyz'
        coordfs.append(xyzf.rsplit('/',1)[-1])
        coordname = xyzft
        # Setting jobname for files + truncated name for queue.
        if len(coordname) > 10:
            nametrunc=coordname[0:6]+coordname[-4:]
        else:
            nametrunc=coordname
        if not os.path.exists(rdir+'/'+nametrunc) and not args.jobdir:
            os.mkdir(rdir+'/'+nametrunc) 
        mdir = rdir+'/'+nametrunc
        if method:
            mmd = '/'+method
            mdir = rdir+'/'+nametrunc+mmd
            if not os.path.exists(mdir):
                os.mkdir(mdir)

        jobdirs.append(mdir)
        shutil.copy2(xyzf,mdir)
        shutil.copy2(xyzf.replace('.xyz','.molinp'),mdir.replace('.xyz','.molinp'))
        try:
            shutil.copy2(xyzf.replace('.xyz','.report'),mdir.replace('.xyz','.report'))
        except:
            pass
    # Check for existence of basis and sanitize name
    if args.basis and len(args.basis) > 1:
        jobparams['BASIS']=args.basis
    if args.correlation and len(args.correlation) > 1:
        jobparams['CORRELATION']=args.correlation
    if method and len(method) > 1:
        jobparams['EXCHANGE']=method
    if not args.unrestricted:
        jobparams['UNRESTRICTED']='false'
    if (args.runtyp and 'en' in args.runtyp.lower()):
        jobparams['run'] = 'SP'
    elif (args.runtyp and 'ts' in args.runtyp.lower()):
        jobparams['run'] = 'TS'
    # Just carry over spin and charge keywords if they're set. Could do checks, none for now.
    if args.spin:
       jobparams['SPIN']=args.spin
    if args.charge:
       jobparams['CHARGE']=args.charge
    # Now we're ready to start building the input file and the job script
    for i,jobd in enumerate(jobdirs):
        output=open(jobd+'/qch.inp','w')
        f=open(jobd+'/'+coordfs[i])
        s0 = f.readlines()[2:] # read coordinates
        f.close()
        # if separate split to two molecules
        if args.bsep and '--' in ''.join(s0):
            idxsplit = [isdx for isdx, ss in enumerate(s0) if '--' in ss][0]
            s = '--\n'+jobparams['CHARGE']+' '+jobparams['SPIN']+'\n'
            s += ''.join(s0[:idxsplit])
            s += '--\n0 1\n'
            s += ''.join(s0[idxsplit+3:])
        else:
            s = s0
        # write rem block
        output.write('$rem\nUNRESTRICTED\t\t' + jobparams['UNRESTRICTED'])
        output.write('\nBASIS\t\t'+jobparams['BASIS']+'\nJOBTYPE\t\t'+jobparams['JOBTYPE'])
        output.write('\nEXCHANGE\t\t'+jobparams['EXCHANGE']+'\nCORRELATION\t\t')
        output.write(jobparams['CORRELATION']+'\nMAX_SCF_CYCLES\t\t')
        output.write(jobparams['MAX_SCF_CYCLES']+'\nGEOM_OPT_MAX_CYCLES\t\t')
        output.write(jobparams['GEOM_OPT_MAX_CYCLES']+'\nSYMMETRY\t\t'+jobparams['SYMMETRY'])
        output.write('\nPRINT_ORBITALS\t\t'+jobparams['PRINT_ORBITALS']+'\n')
        # write additional options
        if (args.remoption):
            if len(args.remoption)%2 > 0:
                print 'WARNING: wrong number of arguments in -remoption'
            else:
                for elem in range(0,int(0.5*len(args.remoption))):
                    key,val=args.remoption[2*elem],args.remoption[2*elem+1]
                    output.write(key+'\t\t'+val+'\n')
        output.write('$end\n\n')
        # write $molecule block
        output.write('$molecule\n'+jobparams['CHARGE']+' '+jobparams['SPIN']+'\n')
        output.write(''.join(s)+'$end')
        output.close()
    return jobdirs

## Generate MOPAC input files
#  @param args Namespace of arguments
#  @param strfiles List of xyz files produced
#  @param rootdir Root directory 
#  @return List of job directories
def mlpgen(args,strfiles,rootdir):
    # get global variables
    globs = globalvars()
    jobdirs = []
    coordfs = []
    # Initialize the jobparams dictionary with mandatory/useful keywords.
    jobparams = ['EF','PM7','XYZ','HESSIAN']
    spin_keywords={1: 'SINGLET',
                   2: 'DOUBLET',
                   3: 'TRIPLET',
                   4: 'QUARTET',
                   5: 'QUINTET',
                   6: 'SEXTET',
                   7: 'SEPTET'}
    # Overwrite plus add any new dictionary keys from commandline input.       
    for xyzf in strfiles:
        rdir = xyzf.rsplit('/',1)[0]
        xyzft = xyzf.rsplit('/',1)[-1]
        xyzf += '.xyz'
        coordfs.append(xyzf.rsplit('/',1)[-1])
        coordname = xyzft
        # Setting jobname for files + truncated name for queue.
        nametrunc=coordname
        if not os.path.exists(rdir+'/'+nametrunc) and not args.jobdir:
            os.mkdir(rdir+'/'+nametrunc) 
        if args.jobdir:
                mdir = args.jobdir
        else:
            mdir = rdir+'/'+nametrunc
        jobdirs.append(mdir)
#        shutil.copy2(xyzf,mdir)
#        shutil.copy2(xyzf.replace('.xyz','.molinp'),mdir.replace('.xyz','.molinp'))
    # Just carry over spin and charge keywords if they're set. Could do checks, none for now.
    if args.spin:
       jobparams.append(spin_keywords[int(args.spin)])
       jobparams.append('UHF')

    else:
        jobparams.append("SINGLET")
    if args.charge:
       jobparams.append('CHARGE='+str(args.charge))
    # Now we're ready to start building the input file and the job script
    for i,jobd in enumerate(jobdirs):
        output=open(strfiles[i] + '.mop','w')
        f=open(strfiles[i]+'.xyz')
        s = f.readlines()[2:] # read coordinates
        f.close()
        # write rem block
        for terms in jobparams:
            output.write(' '+ terms)
        # write additional options
        if (args.remoption):
            if len(args.remoption)%2 > 0:
                print 'WARNING: wrong number of arguments in -remoption'
            else:
                for elem in range(0,int(0.5*len(args.remoption))):
                    key,val=args.remoption[2*elem],args.remoption[2*elem+1]
                    output.write(key+'\t\t'+val+'\n')
        output.write('\n' + nametrunc+'\n')
        output.write('\n')
        # write $molecule block
        for lines in s:
            ll = lines.split('\t')
            for i,items in enumerate(ll):
                output.write(' '+ items.strip('\n'))
                if i>0:
                    output.write(' 1')
                if i == 3:
                    output.write('\n')
        output.close()
    return jobdirs

## Generate multiple ORCA runs if multiple methods requested
#  @param args Namespace of arguments
#  @param strfiles List of xyz files produced
#  @return List of job directories
def multiogen(args,strfiles):
    method = False
    jobdirs=[]
    if args.method and len(args.method) > 0:
        methods = args.method
        for method in methods:
            jobdirs.append(ogen(args,strfiles,method))
    else:
        jobdirs.append(ogen(args,strfiles,method))
    # remove original files
    for xyzf in strfiles:
        os.remove(xyzf+'.xyz')
        os.remove(xyzf+'.molinp')
        os.remove(xyzf + '.report')
    return jobdirs
## Generate ORCA input files
#  @param args Namespace of arguments
#  @param strfiles List of xyz files produced
#  @param rootdir Root directory 
#  @return List of job directories
def ogen(args,strfiles,method):
    # global variables
    globs = globalvars()
    jobdirs = []
    coordfs = []
    # Initialize the jobparams dictionary with mandatory/useful keywords. TG: removed min_coordinates cartesian
    jobparams={'run': 'Sp',
           'basis': 'def2-TZVP',
           'MaxIter': '500',
           'method': 'B3LYP',
           'spinmult': '1',
           'charge': '0',
           'ERI':'NORI',
           'REL':'',
           'UNO':'',
           'mdci_maxit':'200',
           'mdci_shift':'0.2',
           'HFX':False,
            }
    # if multiple methods requested generate c directories
    # Overwrite plus add any new dictionary keys from commandline input.       
    for xyzf in strfiles:
        rdir = xyzf.rsplit('/',1)[0]
        xyzft = xyzf.rsplit('/',1)[-1]
        xyzf += '.xyz'
        coordfs.append(xyzf.rsplit('/',1)[-1])
        coordname = xyzft
        # Setting jobname for files + truncated name for queue.
        if len(coordname) > 10:
            nametrunc=coordname
        else:
            nametrunc=coordname
        if not os.path.exists(rdir+'/'+nametrunc) and not args.jobdir:
            os.mkdir(rdir+'/'+nametrunc) 
        mdir = rdir+'/'+nametrunc
        if method:
            if method[0]=='U' or method[0]=='u':
                mmd = '/'+method[1:]
            else:
                mmd = '/'+method
            mdir = rdir+'/'+nametrunc+mmd
            if not os.path.exists(mdir):
                os.mkdir(mdir)
        if not args.jobdir:
            jobdirs.append(mdir)
            shutil.copy2(xyzf,mdir)
            shutil.copy2(xyzf.replace('.xyz','.molinp'),mdir.replace('.xyz','.molinp'))
            try:
                shutil.copy2(xyzf.replace('.xyz','.report'),mdir.replace('.xyz','.report'))
            except:
                pass
        elif args.jobdir:
             jobdirs.append(rdir)
    # parse extra arguments
    # Method parsing, does not check if a garbage method is used here:
    unrestricted=False
    if method:
        jobparams['method'] = method
        if args.spin and int(args.spin) > 1:
            unrestricted=True
        #For ORCA, "ro" or "u" is not needed
        if ('u' or 'U') in method[0]:
            jobparams['method'] = method[1:]
            # Unrestricted calculation
        elif ('ro' or 'RO') in method[0]:
            # Restricted calculation
            unrestricted=False
            jobparams['method'] = method[2:]
    else:
        if args.spin and int(args.spin) >= 1:
                jobparams['method'] = 'B3LYP'
                unrestricted=True
        else:
            jobparams['method'] = 'B3LYP'
    print args.method,method,jobparams['method']
    #Check runtype and we accept both ORCA and terachem naming convention 
    if (args.runtyp and 'energy' in args.runtyp.lower()):
        jobparams['run'] = 'Sp'
    elif (args.runtyp and 'sp' in args.runtyp.lower()):
        jobparams['run'] = 'Sp'
    elif (args.runtyp and 'opt' in args.runtyp.lower()):
        jobparams['run'] = 'Opt'
    elif (args.runtyp and 'minimize' in args.runtyp.lower()):
        jobparams['run'] = 'Opt'
    elif (args.runtyp and 'gradient' in args.runtyp.lower()):
        jobparams['run'] = 'EnGrad'
    elif (args.runtyp and 'engrad' in args.runtyp.lower()):
        jobparams['run'] = 'EnGrad'
    # Special sanity check for CCSD(T)
    if jobparams['run'] =='Opt' and 'CC' in jobparams['method']:
        print('''Warning! You requested geometry optimization with Coupled-Cluster methods,
                which is NOT supported. Instead, we will geometry optimize the structure 
                with B3LYP and then conduct CCSD(T) energy calculation on the optimized structure''')
    #TODO: check ORCA dispersion
    if (args.dispersion):
        jobparams['dispersion']=args.dispersion
    # Just carry over spin and charge keywords if they're set. Could do checks, none for now.
    if args.spin:
        jobparams['spinmult']=args.spin
    if args.charge:
        if args.bcharge:
            args.charge = int(args.charge)+int(args.bcharge)
        jobparams['charge']=args.charge
    # Check for existence of basis and sanitize name
    # Read in basis name from args only if it's not the default for terachem
    if args.basis and args.basis !='lacvps_ecp' :
        jobparams['basis']=args.basis
    if not jobparams.has_key('DIISMaxEq'):
        jobparams['DIISMaxEq']=15
    # Overwrite plus add any new dictionary keys from commandline input.       
    if args.qoption:
        if len(args.qoption)%2!=0:
                print 'WARNING: wrong number of arguments in -qoption'
        else:
            for elem in range(0,int(0.5*len(args.qoption))):
                key,val=args.qoption[2*elem],args.qoption[2*elem+1]
                jobparams[key]=val
    # Extra keywords for unrestricted. 
    if unrestricted:
       # If running unrestricted, assume convergence will be more difficult for now.
       jobparams['scf']='SlowConv' 
       jobparams['UNO']='UNO'
       if not jobparams.has_key('levelshift'):
          jobparams['levelshift']='yes'
       elif jobparams['levelshift'] != 'yes':
          print("Warning! You're doing an unrestricted calculation but have set levelshift = %s" %(jobparams['levelshift']))
       if not jobparams.has_key('levelshiftval'):
           if jobparams.has_key('levelshiftvala'):
              jobparams['levelshiftval']=jobparams['levelshiftvala']
           elif jobparams.has_key('levelshiftvalb'):
              jobparams['levelshiftval']=jobparams['levelshiftvalb']
           else:
               jobparams['levelshiftval']=0.25
       if not jobparams.has_key('ErrOff'):
           jobparams['ErrOff']=0.00001
    # Now we're ready to start building the input file
    if not args.jobdir:
        for i,jobd in enumerate(jobdirs):
            output=open(jobd+'/orca.in','w')
            output.write('# file created with %s\n' % globs.PROGRAM)
            if 'CC' in jobparams['method'] and jobparams['run']=='Opt':
               params0=jobparams.copy()
               params0['method']='B3LYP'
               ogenwrt(output,params0,coordfs[i])
               output.write('\n$new_job\n')
               jobparams['run']='Sp'
               ogenwrt(output,jobparams,'')
            else:
               ogenwrt(output,jobparams,coordfs[i])
            output.close()
    elif args.jobdir:
        for i,jobd in enumerate(jobdirs):
            print('jobd is ' + jobd)
            if args.name:
                output=open(jobd+ '/'+args.name + '.in','w')
            else:
                output=open(jobd+'/orca.in','w')
            output.write('# file created with %s\n' % globs.PROGRAM)
            if 'CC' in jobparams['method'] and jobparams['run']=='Opt':
               params0=jobparams.copy()
               params0['method']='B3LYP'
               ogenwrt(output,params0,coordfs[i])
               output.write('\n$new_job\n')
               jobparams['run']='Sp'
               ogenwrt(output,jobparams,'')
            else:
               ogenwrt(output,jobparams,coordfs[i])
            output.close()
    return jobdirs

## Writeout a single calculation block for ORCA input files
#  @param output File for writing ORCA input
#  @param jobparams ORCA input parameters
#  @param xyzf Name for xyz file
#  @return List of job directories
def ogenwrt(output,jobparams,xyzf):
    # write the first line of simple keywords
    output.write('!'+jobparams['method']+' ')
    output.write(jobparams['basis']+' ')
    output.write(jobparams['ERI']+' ')
    if jobparams['REL']:
      output.write(jobparams['REL']+' ')
    output.write(jobparams['UNO']+' ')
    output.write(jobparams['run']+'\n\n')
    # write scf convergence mode
    if jobparams.has_key('scf'):
       output.write('!'+jobparams['scf']+'\n')
    # write the scf control block
    output.write('%scf\n')
    output.write('MaxIter '+jobparams['MaxIter']+'\n')
    if jobparams['levelshift']=='yes':
       output.write('Shift Shift '+str(jobparams['levelshiftval'])+' ErrOff '+ str(jobparams['ErrOff'])+'  end\n')
    output.write('DIISMaxEq '+str(jobparams['DIISMaxEq'])+'\n')
    output.write('end\n\n')
    # write the method block to control HFX 
    if not (('CC' or 'HF') in jobparams['method']):
       if jobparams['HFX']:
           output.write('%method\n')
           output.write('ScalHFX = '+jobparams['HFX']+'\n')
           output.write('ScalDFX = '+str(1-float(jobparams['HFX']))+'\n')
           output.write('end\n\n')
    # write the mdci block for CCSD(T)
    if 'CCSD' in jobparams['method']:
        output.write('%mdci\n')
        if jobparams['UNO']:
           output.write('UseQROs true\n')
        output.write('maxiter '+jobparams['mdci_maxit']+'\n')
        output.write('Lshift '+jobparams['mdci_shift']+'\n')
        output.write('end\n\n')
    # write the coordinate block
    output.write('*xyzfile '+str(jobparams['charge'])+' '+str(jobparams['spinmult'])+' '+xyzf+'\n')
    #output.write(''.join(s0)+'*\n')

## Generate MOLCAS input files
#  @param args Namespace of arguments
#  @param strfiles List of xyz files produced
#  @param rootdir Root directory 
#  @return List of job directories
def molcgen(args,strfiles,method):
    # global variables
    globs = globalvars()
    jobdirs = []
    coordfs = []
    # Initialize the jobparams dictionary with mandatory/useful keywords. TG: removed min_coordinates cartesian
    jobparams={'Group': 'Nosym',
           'method': 'CASSCF',
           'spin': '1',
           'charge': '0',
          # 'nactel':'2',
          # 'frozen':'0',
           #'ras2':'12',
           'ciroot':'1 1 ;1',
            'ITER': '1000,100',
            'multistate':'1 1',
            'imaginary':'0.1',
            'ipeashift':'0.25',
            'density':'no',
            'grid_it':'no',
            'gridtype':'TOTAL',
            'NPOINTS':'100 100 100',
            }
    # if multiple methods requested generate c directories
    # Overwrite plus add any new dictionary keys from commandline input.       
    for xyzf in strfiles:
        rdir = xyzf.rsplit('/',1)[0]
        xyzft = xyzf.rsplit('/',1)[-1]
        xyzf += '.xyz'
        coordfs.append(xyzf.rsplit('/',1)[-1])
        coordname = xyzft
        # Setting jobname for files + truncated name for queue.
        if len(coordname) > 10:
            nametrunc=coordname
        else:
            nametrunc=coordname
        if not os.path.exists(rdir+'/'+nametrunc) and not args.jobdir:
            os.mkdir(rdir+'/'+nametrunc) 
        mdir = rdir+'/'+nametrunc
        if method:
            if method[0]=='U' or method[0]=='u':
                mmd = '/'+method[1:]
            else:
                mmd = '/'+method
            mdir = rdir+'/'+nametrunc+mmd
            if not os.path.exists(mdir):
                os.mkdir(mdir)
        if not args.jobdir:
            jobdirs.append(mdir)
            shutil.copy2(xyzf,mdir)
            shutil.copy2(xyzf.replace('.xyz','.molinp'),mdir.replace('.xyz','.molinp'))
            try:
                shutil.copy2(xyzf.replace('.xyz','.report'),mdir.replace('.xyz','.report'))
            except:
                pass
        elif args.jobdir:
             jobdirs.append(rdir)
    # parse extra arguments
    # Method parsing, does not check if a garbage method is used here:
    if method:
        jobparams['method'] = method
    else:
        jobparams['method'] = 'CASSCF'
    print args.method,method,jobparams['method']
    #Check runtype
    if (args.runtyp and 'energy' in args.runtyp.lower()):
        jobparams['run'] = 'energy'
    else:
        print('''Warning! Currently MOLCAS input file generation is only supported for
                single point energy. For other types of calculation requested, the input
                file is generated for single point energy instead''')
    # Just carry over spin and charge keywords if they're set. Could do checks, none for now.
    if args.spin:
        jobparams['spin']=str(args.spin)
    if args.charge:
        if args.bcharge:
            args.charge = int(args.charge)+int(args.bcharge)
        jobparams['charge']=str(args.charge)
    # Check for existence of basis and sanitize name
    # Automatically assign basis based on element
    if args.basis and args.basis !='lacvps_ecp' :
        jobparams['basis']=args.basis
    elif (not args.basis) or args.basis =='lacvps_ecp':
        temp = mol3D()
        jobparams['basis']=molcbasis(strfiles,'ANO-rcc')
    # Overwrite plus add any new dictionary keys from commandline input.       
    if args.qoption:
        if len(args.qoption)%2!=0:
                print 'WARNING: wrong number of arguments in -qoption'
        else:
            for elem in range(0,int(0.5*len(args.qoption))):
                key,val=args.qoption[2*elem],args.qoption[2*elem+1]
                jobparams[key]=val
    #Check which paramters are missing
    #Check and automatically assign number of active electrons
    if not jobparams.has_key('nactel'):
       oxnum = 0 #oxidation state number
       if args.oxstate in romans.keys():
           oxnum = int(romans[args.oxstate])
       else:
           oxnum = int(args.oxstate)
       jobparams['nactel']=molcnactels(strfiles,oxnum)
    else:
       nactel=int(jobparams['nactel'])
       jobparams['nactel']=[ nactel for i in range(0,len(strfiles))]
    #Check and automatically assign number of frozen orbitals for CASSCF
    if not jobparams.has_key('frozen'):
       jobparams['frozen']=molcfrozens(strfiles) 
    else:
       frozen=int(jobparams['frozen'])
       jobparams['frozen']=[ frozen for i in range(0,len(strfiles))]
    #Check and automatically assign number of frozen orbitals for ras2
    if not jobparams.has_key('ras2'):
       jobparams['ras2']=molcras2s(strfiles)
    else:
       ras2=int(jobparams['ras2'])
       jobparams['ras2']=[ ras2 for i in range(0,len(strfiles))]
    #Check key for grid_it. Overwrite the default in case 
    # the command line input is in different case
    for key in jobparams.keys():
        if 'grid_it' in key.lower() and key!='grid_it':
            jobparams['grid_it']=jobparams[key]
            break

    # Now we're ready to start building the input file
    if not args.jobdir:
        for i,jobd in enumerate(jobdirs):
            output=open(jobd+'/molcas.input','w')
            output.write('# file created with %s\n' % globs.PROGRAM)
            molcwrt(output,jobparams,coordfs[i],i)
            output.close()
    elif args.jobdir:
        for i,jobd in enumerate(jobdirs):
            print('jobd is ' + jobd)
            if args.name:
                output=open(jobd+ '/'+args.name + '.in','w')
            else:
                output=open(jobd+'/molcas.input','w')
            output.write('# file created with %s\n' % globs.PROGRAM)
            molcwrt(output,jobparams,coordfs[i],i)
            output.close()
    return jobdirs

## Writeout a single calculation block for ORCA input files
#  @param output File for writing ORCA input
#  @param jobparams ORCA input parameters
#  @param xyzf Name for xyz file
#  @param xyzind Index for xyz file in all generated xyz files
#  @return List of job directories
def molcwrt(output,jobparams,xyzf,xyzind):
    # write the gateway block
    output.write('&gateway\n')
    output.write('Coord='+xyzf+'\n')
    output.write('basis='+jobparams['basis']+'\n')
    output.write('Group='+jobparams['Group']+'\n')
    # write SEWARD block. Hardcode for now
    output.write('&SEWARD\nCHOL\nR02O\n')
    # write RASSCF block
    output.write('&RASSCF\n')
    output.write('  charge='+jobparams['charge']+'\n')
    output.write('  spin='+jobparams['spin']+'\n')
    output.write('  nactel='+str(jobparams['nactel'][xyzind])+' 0 0\n')
    output.write('  frozen='+str(jobparams['frozen'][xyzind])+'\n')
    output.write('  ciroot='+jobparams['ciroot']+'\n')
    output.write('  ras2='+str(jobparams['ras2'][xyzind])+'\n')
    output.write('  ITER='+jobparams['ITER']+'\n')
    # write the CASPT2 block 
    if 'pt2' in jobparams['method'].lower():
        output.write('&CASPT2\n')
        output.write('   multistate='+jobparams['multistate']+'\n')
        output.write('   imaginary='+jobparams['imaginary']+'\n')
        output.write('   ipeashift='+jobparams['ipeashift']+'\n')
        if jobparams['density']=='yes':
            output.write('   density\n')
    # write the GRID_IT block
    if jobparams['grid_it'] == 'yes':
        output.write('&GRID_IT\n')
        output.write(jobparams['gridtype']+'\n')
        output.write('NPOINTS\n'+jobparams['NPOINTS']+'\n')

## Generate multiple MOLCAS runs if multiple methods requested
#  @param args Namespace of arguments
#  @param strfiles List of xyz files produced
#  @return List of job directories
def multimolcgen(args,strfiles):
    method = False
    jobdirs=[]
    if args.method and len(args.method) > 0:
        methods = args.method
        for method in methods:
            jobdirs.append(molcgen(args,strfiles,method))
    else:
        jobdirs.append(molcgen(args,strfiles,method))
    # remove original files
    for xyzf in strfiles:
        os.remove(xyzf+'.xyz')
        os.remove(xyzf+'.molinp')
        os.remove(xyzf + '.report')
    return jobdirs
## Generate MOLCAS basis keyword for a given mol3D
#  @param strfiles List of xyz files produced 
#  @param basistyp The type of basis set
#  @return String of the basis specification
def molcbasis(strfiles,basistyp):
    #List of Sets for elem
    # elems[i] contains elements for i-th row
    elems=[]
    for i in range(0,8):
        elems.append(set())
    #collect elements by rows in the periodic table
    for i in range(0,len(strfiles)):
        temp = mol3D()
        temp.readfromxyz(strfiles[i])
        for atom in temp.getAtoms():
            atno=atom.atno
            sym=atom.symbol()
            if atno<=2:
                elems[1].add(sym)
            elif atno<=10:
                elems[2].add(sym)
            elif atno<=18:
                elems[3].add(sym)
            elif atno<=36:
                elems[4].add(sym)
            elif atno<=54:
                elems[5].add(sym)
            elif atno<=86:
                elems[6].add(sym)
            else:
                elems[7].add(sym)
    basis=''
    #First check whether very heavy elems exist
    for i in range(5,8):
        if len(elems[i]) > 0:
            unsupported=''
            while len(elems[i])>0:
                unsupported+=(elems[i].pop()+',')
            print('Warning! Automatic basis generation not available for heavy elemts in row >4 yet!')
            print('Basis was not generated for '+unsupported)
            break
    if basistyp == 'ANO-rcc':
        while len(elems[1]) > 0:
            elem=elems[1].pop()
            if basis!='':
                basis+=','
            basis+=elem+'.'+basistyp+'...3s1p.'
        while len(elems[2]) > 0:
            elem=elems[2].pop()
            if basis!='':
                basis+=','
            basis+=elem+'.'+basistyp+'...4s3p2d1f.'
        while len(elems[3])>0:
            elem=elems[3].pop()
            if basis!='':
                basis+=','
            basis+=elem+'.'+basistyp+'... 5s4p3d2f.'
        while len(elems[4])>0:
            elem=elems[4].pop()
            if basis!='':
                basis+=','
            basis+=elem+'.'+basistyp+'...7s6p5d3f2g1h.'
    else:
        print('''Automatic Basis generation for basis type
        other than ANO-rcc is not supported yet''') 
    return basis

## Determine MOLCAS CASSCF active space for a given mol3D
#  @param strfiles List of xyz files produced 
#  @return List of the active spaces
def molcras2s(strfiles):
    print('Warning! "ras2" active space is automatically generated and may need adjustment! ')
    ras2s=[]
    for i in range(0,len(strfiles)):
        temp = mol3D()
        temp.readfromxyz(strfiles[i])
        metal_ind = temp.findMetal() 
        ras2=0
        for ind in metal_ind:
            metal=temp.getAtom(ind)
            atno=metal.atno
            if (atno>24 and atno<31) or (atno>42 and atno<49):
                ras2+=12 #double d shell+2 bonding
            else:
                ras2+=7 #single d shell + bonding
        ras2s.append(ras2)
    return ras2s

## Determine MOLCAS CASSCF active electrons for a given mol3D
#  @param strfiles List of xyz files produced 
#  @return List of the active spaces
def molcnactels(strfiles,oxnum):
    print('Warning! "nactel" is automatically generated and may need adjustment! ')
    nactels=[]
    for i in range(0,len(strfiles)):
        temp = mol3D()
        temp.readfromxyz(strfiles[i])
        metal_ind = temp.findMetal() 
        nactel=0
        for ind in metal_ind:
            metal=temp.getAtom(ind)
            atno=metal.atno
            if atno>20 and atno<31 : #1st row TM
                nactel+=atno-18-oxnum+4 #4s3d electron + 4 bonding orbital electrons
            else:
                print('Warning! Automatic assignment of "nactel"is not available')
                print ('for heavy atom like '+ temp.getAtom(ind).symbol()+'yet')
        nactels.append(nactel)
    return nactels

## Determine MOLCAS CASSCF frozen orbitals for a given mol3D
#  @param strfiles List of xyz files produced 
#  @return List of the active spaces
def molcfrozens(strfiles):
    frozens=[]
    for i in range(0,len(strfiles)):
        frozen=0
        temp = mol3D()
        temp.readfromxyz(strfiles[i])
        for atom in temp.getAtoms():
            atno=atom.atno
            if atno >2 and atno <=10:
                frozen+=1 #1s
            elif atno > 10 and atno<=18:
                frozen+=5 #1s2s2p Not super sure about the 3rd row
            elif atno > 18 and atno <=36: 
                frozen+=5  #1s2s2p
            elif atno > 36 and atno <=54:
                frozen+=9   #1s2s2p3s3p
            elif atno > 54:
                print('Warning! Automatic assignment of "frozen"is not available')
                print ('for heavy atom like '+ temp.getAtom(ind).symbol()+'yet')
        frozens.append(frozen)
    return frozens
