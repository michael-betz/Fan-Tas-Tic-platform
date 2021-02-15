"""Example external platform for MPF."""

from setuptools import setup

setup(

    name='fantastic_platform',
    version='0.54',
    description='Mission Pinball external platform for the Fantastic controller board',
    url='https://github.com/yetifrisstlama/Fan-Tas-Tic-platform',
    author='Michael Betz',
    author_email='michibetz@gmail.com',
    license='BSD',
    keywords='pinball',
    include_package_data=True,

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Natural Language :: English',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Topic :: Artistic Software',
        'Topic :: Games/Entertainment :: Arcade'
    ],

    # MANIFEST.in picks up the rest
    packages=['fantastic_platform'],

    install_requires=['mpf'],

    entry_points='''
    [mpf.platforms]
    fantastic_platform=fantastic_platform.fantastic_hardware_platform:FanTasTicHardwarePlatform
    '''
)
