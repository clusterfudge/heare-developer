from setuptools import find_namespace_packages, setup

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="heare-developer",
    use_scm_version=True,
    packages=find_namespace_packages(include=["heare*"]),
    include_package_data=True,
    install_requires=requirements,
    setup_requires=["setuptools_scm"],
    entry_points={
        "console_scripts": [
            "heare-developer=heare.developer.cli:main",
            "heare-console=heare.developer.terminal:main",
            "heare-pm=heare.pm.project.cli:main",
        ],
    },
    author="Sean Fitzgerald",
    author_email="sean@fitzgeralds.me",
    description="A command-line coding agent.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/heare-developer",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
