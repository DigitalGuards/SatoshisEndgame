from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="satoshis-endgame",
    version="0.1.0",
    author="SatoshisEndgame Contributors",
    description="Bitcoin quantum vulnerability monitoring system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/satoshis-endgame",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.10",
    install_requires=[
        "aiohttp>=3.10.10",
        "bitcoinlib>=0.6.15",
        "sqlalchemy>=2.0.36",
        "asyncpg>=0.30.0",
        "apscheduler>=3.10.4",
        "structlog>=24.4.0",
        "pydantic>=2.9.2",
        "pydantic-settings>=2.6.1",
        "discord-webhook>=1.3.1",
        "numpy>=1.26.4",
        "python-dotenv>=1.0.1",
        "click>=8.1.8",
        "rich>=13.9.4",
    ],
    entry_points={
        "console_scripts": [
            "satoshis-endgame=src.cli:main",
        ],
    },
)