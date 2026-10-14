from setuptools import find_packages, setup

package_name = 'bras_controle'

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
    maintainer_email='etudiant@roboforge.example',
    description='Cinématique du bras de tri du parcours « Programmer un bras robotique avec ROS 2 »',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'cinematique_directe = bras_controle.cinematique_directe:main',
            'cinematique_inverse = bras_controle.cinematique_inverse:main',
        ],
    },
)
