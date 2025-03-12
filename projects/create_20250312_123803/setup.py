from setuptools import setup, find_packages

# Define the package name and version
PACKAGE_NAME = 'simple_calculator'
VERSION = '0.1.0'

# Define the package description and long description
DESCRIPTION = 'A simple calculator application using Python and Tkinter.'
with open('README.md', 'r') as fh:
    LONG_DESCRIPTION = fh.read()

# Define the URL for your project
URL = 'https://github.com/yourusername/simple-calculator'

# Define the author and email
AUTHOR = 'Your Name'
EMAIL = 'your.email@example.com'

# Define the classifiers that describe your package
CLASSIFIERS = [
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Education',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
    'Programming Language :: Python :: 3.10',
]

# Define the dependencies required for your package
INSTALL_REQUIRES = [
    # List any external packages that your project depends on here.
    # For example: 'numpy', 'pandas'
]

# Define the entry points for your package
ENTRY_POINTS = {
    'console_scripts': [
        'simple_calculator=main:main',
    ],
}

# Define additional package data (if needed)
PACKAGE_DATA = {
    # Include any non-code files that should be included in the package.
    # For example: {'your_package_name': ['data/*.txt']}
}

setup(
    name=PACKAGE_NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type='text/markdown',
    url=URL,
    author=AUTHOR,
    author_email=EMAIL,
    classifiers=CLASSIFIERS,
    install_requires=INSTALL_REQUIRES,
    entry_points=ENTRY_POINTS,
    packages=find_packages(),
    package_data=PACKAGE_DATA,
    include_package_data=True,
    python_requires='>=3.6',
)