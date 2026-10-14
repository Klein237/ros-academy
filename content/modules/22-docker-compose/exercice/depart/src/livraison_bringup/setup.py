from glob import glob

from setuptools import find_packages, setup

package_name = 'livraison_bringup'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Équipe RoboForge',
    maintainer_email='equipe@roboforge.example',
    description='Démarrage du robot de livraison, empaqueté dans une image Docker',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'etat = livraison_bringup.etat:main',
        ],
    },
)
