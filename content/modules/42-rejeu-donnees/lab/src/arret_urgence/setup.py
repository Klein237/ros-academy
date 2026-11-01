from setuptools import find_packages, setup

package_name = 'arret_urgence'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='etudiant',
    maintainer_email='etudiant@roboforge.local',
    description="Arrêt d'urgence du robot de livraison",
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'arret_urgence = arret_urgence.noeud:main',
            'lidar_simule = arret_urgence.lidar_simule:main',
        ],
    },
)
