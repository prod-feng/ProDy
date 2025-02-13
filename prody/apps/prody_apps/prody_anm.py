# -*- coding: utf-8 -*-
"""Perform ANM calculations and output the results in plain text, NMD, and
graphical formats."""

from ..apptools import *
from .nmaoptions import *
from . import nmaoptions

__all__ = ['prody_anm']

DEFAULTS = {}
HELPTEXT = {}
for key, txt, val in [
    ('model', 'index of model that will be used in the calculations', 1),
    ('altloc', 'alternative location identifiers for residues used in the calculations', "A"),
    ('cutoff', 'cutoff distance (A)', '15.'),
    ('gamma', 'spring constant', '1.'),
    ('sparse', 'use sparse matrices', False),
    ('kdtree', 'use kdtree for Hessian', False),    
    ('zeros', 'calculate zero modes', False),
    ('turbo', 'use memory-intensive turbo option for modes', False),

    ('outbeta', 'write beta-factors calculated from ANM modes', False),
    ('hessian', 'write Hessian matrix', False),
    ('kirchhoff', 'write Kirchhoff matrix', False),
    ('figcmap', 'save contact map (Kirchhoff matrix) figure', False),
    ('figbeta', 'save beta-factors figure', False),
    ('figmode', 'save mode shape figures for specified modes, '
                'e.g. "1-3 5" for modes 1, 2, 3 and 5', '')]:

    DEFAULTS[key] = val
    HELPTEXT[key] = txt

DEFAULTS.update(nmaoptions.DEFAULTS)
HELPTEXT.update(nmaoptions.HELPTEXT)

DEFAULTS['prefix'] = '_anm'


def prody_anm(pdb, **kwargs):
    """Perform ANM calculations for *pdb*.

    """

    for key in DEFAULTS:
        if key not in kwargs:
            kwargs[key] = DEFAULTS[key]

    from os.path import isdir, join, exists
    outdir = kwargs.get('outdir')
    if not isdir(outdir):
        raise IOError('{0} is not a valid path'.format(repr(outdir)))

    import numpy as np
    import prody
    LOGGER = prody.LOGGER

    selstr = kwargs.get('select')
    prefix = kwargs.get('prefix')
    sparse = kwargs.get('sparse')
    kdtree = kwargs.get('kdtree')
    nmodes = kwargs.get('nmodes')
    model = kwargs.get('model')
    altloc = kwargs.get('altloc')
    zeros = kwargs.get('zeros')
    turbo = kwargs.get('turbo')
    membrane = kwargs.get('membrane')

    if membrane and not exists(pdb):
        pdb = prody.fetchPDBfromOPM(pdb)

    pdb = prody.parsePDB(pdb, model=model, altloc=altloc)
    if prefix == '_anm':
        prefix = pdb.getTitle() + '_anm'

    select = pdb.select(selstr)
    if select is None:
        LOGGER.warn('Selection {0} did not match any atoms.'
                    .format(repr(selstr)))
        return
    LOGGER.info('{0} atoms will be used for ANM calculations.'
                .format(len(select)))

    if membrane:
        anm = prody.exANM(pdb.getTitle())
    else:
        anm = prody.ANM(pdb.getTitle())
    try:
        gamma = float(kwargs.get('gamma'))
        LOGGER.info("Using gamma {0}".format(gamma))
    except ValueError:
        try:
            gamma = eval('prody.' + kwargs.get('gamma'))
            gamma = gamma(select)
            LOGGER.info("Using gamma {0}".format(gamma))
        except NameError:
            raise NameError("Please provide gamma as a float or ProDy Gamma class")
        except TypeError:
            raise TypeError("Please provide gamma as a float or ProDy Gamma class")
        
    try:
        cutoff = float(kwargs.get('cutoff'))
        LOGGER.info("Using cutoff {0}".format(cutoff))
    except ValueError:
        try:
            import math
            cutoff = eval(kwargs.get('cutoff'))
            LOGGER.info("Using cutoff {0}".format(cutoff))
        except NameError:
            raise NameError("Please provide cutoff as a float or equation using math")
        except TypeError:
            raise TypeError("Please provide cutoff as a float or equation using math")

    nproc = kwargs.get('nproc')
    anm.buildHessian(select, cutoff, gamma, sparse=sparse, kdtree=kdtree)
    anm.calcModes(nmodes, zeros=zeros, turbo=turbo, nproc=nproc)
    
    LOGGER.info('Writing numerical output.')

    if kwargs.get('outnpz'):
        prody.saveModel(anm, join(outdir, prefix), 
                        matrices=kwargs.get('npzmatrices'))

    if kwargs.get('outscipion'):
        prody.writeScipionModes(outdir, anm)

    prody.writeNMD(join(outdir, prefix + '.nmd'), anm, select)

    extend = kwargs.get('extend')
    if extend:
        if extend == 'all':
            extended = prody.extendModel(anm, select, pdb)
        else:
            extended = prody.extendModel(anm, select, select | pdb.bb)
        prody.writeNMD(join(outdir, prefix + '_extended_' +
                       extend + '.nmd'), *extended)

    outall = kwargs.get('outall')
    delim = kwargs.get('numdelim')
    ext = kwargs.get('numext')
    format = kwargs.get('numformat')


    if outall or kwargs.get('outeig'):
        prody.writeArray(join(outdir, prefix + '_evectors'+ext),
                         anm.getArray(), delimiter=delim, format=format)
        prody.writeArray(join(outdir, prefix + '_evalues'+ext),
                         anm.getEigvals(), delimiter=delim, format=format)

    if outall or kwargs.get('outbeta'):
        from prody.utilities import openFile
        fout = openFile(prefix + '_beta'+ext, 'w', folder=outdir)
        fout.write('{0[0]:1s} {0[1]:4s} {0[2]:4s} {0[3]:5s} {0[4]:5s}\n'
                       .format(['C', 'RES', '####', 'Exp.', 'The.']))
        for data in zip(select.getChids(), select.getResnames(),
                        select.getResnums(), select.getBetas(),
                        prody.calcTempFactors(anm, select)):
            fout.write('{0[0]:1s} {0[1]:4s} {0[2]:4d} {0[3]:5.2f} {0[4]:5.2f}\n'
                       .format(data))
        fout.close()

    if outall or kwargs.get('outcov'):
        prody.writeArray(join(outdir, prefix + '_covariance' + ext),
                         anm.getCovariance(), delimiter=delim, format=format)

    if outall or kwargs.get('outcc') or kwargs.get('outhm'):
        cc = prody.calcCrossCorr(anm)
        if outall or kwargs.get('outcc'):
            prody.writeArray(join(outdir, prefix +
                             '_cross-correlations' + ext),
                             cc, delimiter=delim,  format=format)
        if outall or kwargs.get('outhm'):
            prody.writeHeatmap(join(outdir, prefix + '_cross-correlations.hm'),
                               cc, resnum=select.getResnums(),
                               xlabel='Residue', ylabel='Residue',
                               title=anm.getTitle() + ' cross-correlations')

    if outall or kwargs.get('hessian'):
        prody.writeArray(join(outdir, prefix + '_hessian'+ext),
                         anm.getHessian(), delimiter=delim, format=format)

    if outall or kwargs.get('kirchhoff'):
        prody.writeArray(join(outdir, prefix + '_kirchhoff'+ext),
                         anm.getKirchhoff(), delimiter=delim, format=format)

    if outall or kwargs.get('outsf'):
        prody.writeArray(join(outdir, prefix + '_sqflucts'+ext),
                         prody.calcSqFlucts(anm), delimiter=delim,
                         format=format)

    figall = kwargs.get('figall')
    cc = kwargs.get('figcc')
    sf = kwargs.get('figsf')
    bf = kwargs.get('figbeta')
    cm = kwargs.get('figcmap')


    if figall or cc or sf or bf or cm:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            LOGGER.warning('Matplotlib could not be imported. '
                           'Figures are not saved.')
        else:
            prody.SETTINGS['auto_show'] = False
            LOGGER.info('Saving graphical output.')
            format = kwargs.get('figformat')
            width = kwargs.get('figwidth')
            height = kwargs.get('figheight')
            dpi = kwargs.get('figdpi')
            format = format.lower()

            if figall or cc:
                plt.figure(figsize=(width, height))
                prody.showCrossCorr(anm, interactive=False)
                plt.savefig(join(outdir, prefix + '_cc.'+format),
                    dpi=dpi, format=format)
                plt.close('all')

            if figall or cm:
                plt.figure(figsize=(width, height))
                prody.showContactMap(anm, interactive=False)
                plt.savefig(join(outdir, prefix + '_cm.'+format),
                    dpi=dpi, format=format)
                plt.close('all')

            if figall or sf:
                plt.figure(figsize=(width, height))
                prody.showSqFlucts(anm)
                plt.savefig(join(outdir, prefix + '_sf.'+format),
                    dpi=dpi, format=format)
                plt.close('all')

            if figall or bf:
                plt.figure(figsize=(width, height))
                bexp = select.getBetas()
                bcal = prody.calcTempFactors(anm, select)
                plt.plot(bexp, label='Experimental')
                plt.plot(bcal, label=('Theoretical (R={0:.2f})'
                                        .format(np.corrcoef(bcal, bexp)[0,1])))
                plt.legend(prop={'size': 10})
                plt.xlabel('Node index')
                plt.ylabel('Experimental B-factors')
                plt.title(pdb.getTitle() + ' B-factors')
                plt.savefig(join(outdir, prefix + '_bf.'+format),
                    dpi=dpi, format=format)
                plt.close('all')


_ = list(HELPTEXT)
_.sort()
for key in _:

    prody_anm.__doc__ += """
    :arg {0}: {1}, default is ``{2!r}``""".format(key, HELPTEXT[key],
                                                  DEFAULTS[key])

def addCommand(commands):

    subparser = commands.add_parser('anm',
        help='perform anisotropic network model normal mode analysis calculations')

    subparser.add_argument('--quiet', help="suppress info messages to stderr",
        action=Quiet, nargs=0)

    subparser.add_argument('--examples', action=UsageExample, nargs=0,
        help='show usage examples and exit')
    subparser.set_defaults(usage_example=
"""Perform ANM calculations for given PDB structure and output results in NMD
format.  If an identifier is passed, structure file will be downloaded from
the PDB FTP server.

Fetch PDB 1p38, run ANM calculations using default parameters, and write
NMD file:

  $ prody anm 1p38

Fetch PDB 1aar, run ANM calculations using default parameters for chain A
carbon alpha atoms with residue numbers less than 70, and save all of the
graphical output files:

  $ prody anm 1aar -s "calpha and chain A and resnum < 70" -A""",
  test_examples=[0, 1])

    group = addNMAParameters(subparser)

    group.add_argument('-c', '--cutoff', dest='cutoff', type=str,
        default=DEFAULTS['cutoff'], metavar='FLOAT',
        help=HELPTEXT['cutoff'] + ' (default: %(default)s)')

    group.add_argument('-g', '--gamma', dest='gamma', type=str,
        default=DEFAULTS['gamma'], metavar='STR',
        help=HELPTEXT['gamma'] + ' (default: %(default)s)')

    group.add_argument('-C', '--sparse-hessian', dest='sparse', action='store_true',
        default=DEFAULTS['sparse'],
        help=HELPTEXT['sparse'] + ' (default: %(default)s)')

    group.add_argument('-G', '--use-kdtree', dest='kdtree', action='store_true',
        default=DEFAULTS['kdtree'],
        help=HELPTEXT['kdtree'] + ' (default: %(default)s)')

    group.add_argument('-y', '--turbo', dest='turbo', action='store_true',
        default=DEFAULTS['turbo'],
        help=HELPTEXT['turbo'] + ' (default: %(default)s)')

    group.add_argument('-m', '--model', dest='model', type=int,
        metavar='INT', default=DEFAULTS['model'], help=HELPTEXT['model'])

    group.add_argument('-L', '--altloc', dest='altloc', type=str,
        metavar='STR', default=DEFAULTS['altloc'], help=HELPTEXT['altloc'])

    group.add_argument('-w', '--zero-modes', dest='zeros', action='store_true',
        default=DEFAULTS['zeros'], help=HELPTEXT['zeros'])

    group = addNMAOutput(subparser)

    group.add_argument('-b', '--beta-factors', dest='outbeta',
        action='store_true', default=DEFAULTS['outbeta'],
        help=HELPTEXT['outbeta'])

    group.add_argument('-l', '--hessian', dest='hessian',
        action='store_true',
        default=DEFAULTS['hessian'], help=HELPTEXT['hessian'])

    group.add_argument('-k', '--kirchhoff', dest='kirchhoff',
        action='store_true',
        default=DEFAULTS['kirchhoff'], help=HELPTEXT['kirchhoff'])


    group = addNMAOutputOptions(subparser, '_anm')

    group = addNMAFigures(subparser)

    group.add_argument('-B', '--beta-factors-figure', dest='figbeta',
        action='store_true',
        default=DEFAULTS['figbeta'], help=HELPTEXT['figbeta'])

    group.add_argument('-K', '--contact-map', dest='figcmap',
        action='store_true',
        default=DEFAULTS['figcmap'], help=HELPTEXT['figcmap'])

    group = addNMAFigureOptions(subparser)

    subparser.add_argument('pdb', help='PDB identifier or filename')

    subparser.set_defaults(func=lambda ns: prody_anm(ns.__dict__.pop('pdb'),
                                                     **ns.__dict__))

    subparser.set_defaults(subparser=subparser)
