from setuptools import setup, find_packages

setup(
    name="umeqam",
    version="0.1.0",
    description="Runtime epistemic risk engine for AI in regulated industries",
    author="UMEQAM AI Systems",
    author_email="legal@umeqam.com",
    url="https://github.com/umeqam/umeqam-api",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
    ],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)