from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="legacy-protocol",
    version="0.1.0",
    author="LEGACY Protocol Team",
    author_email="team@legacyprotocol.org",
    description="A fractal-based sharded blockchain protocol",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/legacy-protocol/legacy-core",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.900",
            "pytest>=7.0.0",
            "pytest-asyncio>=0.18.0",
            "pytest-cov>=3.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "legacy-node=legacy_blockchain.node:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/legacy-protocol/legacy-core/issues",
        "Source": "https://github.com/legacy-protocol/legacy-core",
        "Documentation": "https://docs.legacyprotocol.org",
    },
)
