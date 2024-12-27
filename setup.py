from setuptools import setup, find_packages

setup(
    name="web-reader",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "beautifulsoup4>=4.12.0",
        "selenium>=4.0.0",
        "langchain>=0.1.0",
        "langchain-ollama>=0.1.0",
        "langgraph>=0.0.1",
        "typing-extensions>=4.0.0"
    ],
    entry_points={
        "console_scripts": [
            "web-reader=src.main:main",
        ],
    },
    python_requires=">=3.10",
    author="Your Name",
    author_email="your.email@example.com",
    description="A natural language screen reader for web content",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    keywords="screen reader, accessibility, web, nlp",
    url="https://github.com/yourusername/web-reader",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Internet :: WWW/HTTP :: Browsers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
    ],
)
