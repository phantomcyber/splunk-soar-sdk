from setuptools import setup, find_packages

setup(
    name="splunk-soar-sdk",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    package_data={
        "soar_sdk": ["shims/phantom/*", "shims/phantom_common/app_interface/*", "templates/base/*", "templates/components/*", "templates/widgets/*"],  # Include all files in shims/phantom
    },
)