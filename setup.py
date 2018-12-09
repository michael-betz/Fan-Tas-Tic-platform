"""Example external platform for MPF."""

from setuptools import setup

setup(

    name='fantastic_platform',
    version='0.1.0',
    description='Mission Pinball external platform for the Fantastic controller board',
    url='https://github.com/yetifrisstlama/Fan-Tas-Tic-platform',
    author='Michael Betz',
    author_email='michibetz@gmail.com',
    license='BSD',
    keywords='pinball',
    include_package_data=True,

    # MANIFEST.in picks up the rest
    packages=['fantastic_platform'],

    install_requires=['mpf'],

    entry_points='''
    [mpf.platforms]
    fantastic_platform=fantastic_platform.fantastic_hardware_platform:FanTasTicHardwarePlatform
    '''
)
